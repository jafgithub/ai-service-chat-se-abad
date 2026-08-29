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
