# The GPU

Everything needed to create the machine and wire it to the service assistant.
The long form, with the reasoning and the screenshots, is the `gpu-setup`
document. This is the short version for whoever is at the keyboard.

## Order

The quota first. Everything else is quick, and none of it can be tested until
that lands.

1. **Quota.** Service Quotas, us-west-2, "Running On-Demand G and VT
   instances". A new account has **0**, and `g6.xlarge` needs **4**. Approval is
   usually hours and can be two days.
2. **IAM user.** `serviceagent-gpu-switch`, no console access, one access key,
   `iam-policy.json` inline. Fill in the account id and the instance id after
   step 3, then come back.
3. **The instance.**
   - AMI: Deep Learning Base OSS Nvidia Driver GPU AMI, Ubuntu 22.04
   - Type: `g6.xlarge`, region us-west-2
   - Storage: 100GB gp3
   - **Shutdown behaviour: stop.** Not terminate. The machine shuts itself
     down, so with the wrong setting here the idle timer deletes it
   - Tag: `AutoStop` = `true`
   - User data: paste `cloud-init.yaml`
4. **Security group.** Inbound `11434` from `35.91.251.211/32` only, and `22`
   from your own address only. Ollama has no authentication of any kind, and an
   open 11434 is a free GPU for whoever scans for it.
5. **Lambda.** `lambda_auto_stop.py`, python3.12, 30 second timeout, execution
   role from `lambda-policy.json`, EventBridge schedule `rate(5 minutes)`.
6. **`.env` on the service assistant**, then restart it:

   ```
   GPU_INSTANCE_ID=i-...
   AWS_REGION=us-west-2
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   ```

   Do not set `OLLAMA_URL`. The address changes every time the machine is
   stopped and started, so it is read from the AWS API instead.

## The two auto-off mechanisms, and why there are two

| | On the GPU | Lambda |
|---|---|---|
| Knows when the last question was | Yes, from Ollama's journal | No, only CPU |
| Survives the machine wedging | **No** | **Yes** |
| Fires at | 20 idle minutes | 45 minutes running, under 5% CPU |

The on-box timer is precise and does the day to day work. The Lambda is the one
that catches a hung machine or one started from the console and forgotten,
which is the failure that actually costs money, because a timer on a hung box
does not run.

## Checking it works

```bash
# on the GPU
systemctl status ollama
systemctl list-timers ollama-idle-off.timer
curl -s localhost:11434/api/tags | head
sudo /usr/local/bin/ollama-idle-off.sh      # says why it is or is not stopping

# from the service assistant, proving the security group
curl -s --max-time 5 http://<gpu-ip>:11434/api/tags | head
```

Then the one that matters: switch the admin panel to the GPU, stop the
instance, and ask a question. It must be answered by Gemini and the panel must
say so. That is what happens in front of a client when somebody forgets to
press start.

## Cost

About $0.80 an hour while running, plus about $8 a month for the disk whether
it runs or not. Left running, it is roughly $580 a month. The whole gap between
those two numbers is the auto-off, which is why it has two mechanisms.

---

# What actually happened, 2026-08-30

The client's key arrived (`ollm_admin`) and all of the above was attempted for
real. Two things stop a `g6.xlarge` existing today, and **only the account
owner can clear either**.

## Blocker 1: the account is on the AWS Free Tier plan

`RunInstances` refuses outright:

    InvalidParameterCombination: The specified instance type is not eligible
    for Free Tier.

The only types this account may launch are `t3.micro`, `t3.small`,
`t4g.micro`, `t4g.small`, `c7i-flex.large` and `m7i-flex.large`. No GPU type is
free tier eligible, so no quota increase can help until the account is moved to
a paid plan in Billing. This is not the quota, and it is not something an IAM
user can change.

## Blocker 2: the G quota is 0

As the section above predicted. A request for 4 vCPUs was submitted on
2026-08-30 and is pending:

    id 256c84003f43406fb6217f053ce0b130J36szWFS   desired 4   PENDING

Both have to clear. Neither can be worked around from here.

## What was built anyway, and proved

Account `253918336085`, us-west-2, which is **not** the account the three
application boxes live in (`952427475294`). So this is cross account, and the
private networking in `gpu-setup` does not apply: the apps reach the model over
the public internet, and the security group is the only thing in front of it.

    security group  sg-06ad9397831595b43   ollama-gpu
      11434  from 35.91.251.211/32, 54.188.207.85/32, 54.254.25.0/32
      22     from the operator's own address
      and nothing else, ever

    key pair        ollama-gpu (ed25519)
    instance        i-040f1f3ecffb0356e   m7i-flex.large, 8 GB, Ubuntu 24.04
    model           llama3.1:8b, the one the application is configured for

Verified, in this order:

1. `11434` refused from a machine that is not one of the three, and answered
   from all three of them. The boundary is real, not assumed.
2. A generation cross account, over the internet: 19s for a trivial prompt.
3. The switch set to `gpu`, a real resident question answered from the real
   model, grounded, citing Rule 2 and Rule 18: `served_by: gpu`,
   `fell_back: false`. 70 seconds, because this is a CPU.
4. `OLLAMA_TIMEOUT_SECONDS` is 45 and an 8B model on 2 CPU cores cannot finish
   a retrieval prompt inside it, so the first three questions fell back to
   Gemini with `The GPU stopped answering mid-question.` **That is the design
   working**, not a fault: three residents got correct answers and the panel
   said who wrote them. 45s stays, because an L4 answers in a few seconds.
5. The instance stopped, as the idle timer will stop it every day. A resident
   asked a question and got a correct answer **in 1.6 seconds** from Gemini,
   with the panel reporting `fell_back: true` and naming the reason.

The instance is left **stopped**. Compute is not billed while stopped; the
40GB volume is, at roughly $3.20 a month.

## Turning it into the real thing, once both blockers clear

Not a rebuild. Stop it, change the type, start it:

    aws ec2 modify-instance-attribute --instance-id i-040f1f3ecffb0356e \
        --instance-type g6.xlarge

Then re-run the Ollama installer on the box: it detects the NVIDIA card and
pulls the driver itself. Everything else, the AMI, the security group, the
model, the idle timer, the address the applications call, is already right.

## The one bug this found in the automation

`ollama pull` from cloud-init dies with `panic: $HOME is not defined`. The CLI
reads `$HOME` to find its model directory and cloud-init has none, so the first
unattended build finished with Ollama running and no model in it, which looks
from the outside exactly like a model that failed to download. `userdata.sh`
now pulls through the HTTP API instead, and so does the idle check.

## The scripts here

    awsenv.py      reads the key out of the client's CSV so it is never typed
    survey.py      what exists, and what the quota actually is
    quota.py       reads the request history and submits the increase
    provision.py   security group and key pair, idempotent
    launch.py      the instance, with shutdown behaviour set to stop
    userdata.sh    the unattended install, including the idle timer

Run them with any Python that has boto3:

    .venv/bin/python deploy/gpu/survey.py
