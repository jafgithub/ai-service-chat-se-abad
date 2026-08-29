"""
Stop any GPU that has been left running. The backstop, not the primary.

The machine stops itself after 20 idle minutes, and that mechanism is the
precise one: it reads Ollama's own journal, so it knows exactly when the last
question arrived. What it cannot do is survive the machine wedging, because a
timer on a hung box does not run. That is the failure that costs real money,
and it is the only reason this exists.

It also catches the other case the on-box timer cannot: an instance started
from the AWS console by hand, on which nobody ever ran a question, so there is
nothing in the journal to be idle about.

Deliberately cruder than the on-box timer. It cannot see Ollama, so it uses
CPU, which on an idle Ollama box sits near zero and during generation does not.
Crude is fine for a backstop whose job is to catch a machine nobody is looking
at.

    Runtime      python3.12
    Trigger      EventBridge Scheduler, rate(5 minutes)
    Timeout      30 seconds
    Scope        every instance tagged AutoStop=true

Environment variables, all optional:

    IDLE_MINUTES     how far back to look at CPU        default 30
    GRACE_MINUTES    never stop a machine younger than  default 45
    CPU_THRESHOLD    percent, below which it is idle    default 5
    MAX_RUNTIME_HOURS  stop regardless after this       default 0 (off)
"""

import datetime as dt
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

IDLE_MINUTES = int(os.environ.get("IDLE_MINUTES", "30"))
GRACE_MINUTES = int(os.environ.get("GRACE_MINUTES", "45"))
CPU_THRESHOLD = float(os.environ.get("CPU_THRESHOLD", "5"))
MAX_RUNTIME_HOURS = float(os.environ.get("MAX_RUNTIME_HOURS", "0"))

TAG = "AutoStop"


def lambda_handler(event, context):
    ec2 = boto3.client("ec2")
    cloudwatch = boto3.client("cloudwatch")

    found = ec2.describe_instances(Filters=[
        {"Name": f"tag:{TAG}", "Values": ["true"]},
        {"Name": "instance-state-name", "Values": ["running"]},
    ])

    stopped, examined = [], 0
    now = dt.datetime.now(dt.timezone.utc)

    for reservation in found["Reservations"]:
        for instance in reservation["Instances"]:
            examined += 1
            instance_id = instance["InstanceId"]
            running_for = (now - instance["LaunchTime"]).total_seconds() / 60

            if MAX_RUNTIME_HOURS and running_for >= MAX_RUNTIME_HOURS * 60:
                logger.info("%s has run for %.0f minutes, over the hard cap",
                            instance_id, running_for)
                stopped.append(instance_id)
                continue

            # A machine somebody started two minutes ago is not idle, it is new.
            if running_for < GRACE_MINUTES:
                logger.info("%s running %.0f minutes, inside the %d minute grace",
                            instance_id, running_for, GRACE_MINUTES)
                continue

            if _is_busy(cloudwatch, instance_id):
                logger.info("%s is doing something; leaving it alone", instance_id)
                continue

            logger.info("%s idle for %d minutes; stopping it",
                        instance_id, IDLE_MINUTES)
            stopped.append(instance_id)

    if stopped:
        ec2.stop_instances(InstanceIds=stopped)
        logger.info("stopped %s", ", ".join(stopped))

    return {"examined": examined, "stopped": stopped}


def _is_busy(cloudwatch, instance_id: str) -> bool:
    """Has this instance used any CPU worth speaking of recently?

    Maximum rather than Average on purpose: one busy minute in thirty means
    somebody asked a question, and an average would drown that out entirely.

    No datapoints means CloudWatch has nothing to say, which happens to an
    instance that has only just started. Treated as busy, because the expensive
    mistake here is stopping a machine somebody is using, not leaving one
    running for five more minutes until the next run.
    """
    now = dt.datetime.now(dt.timezone.utc)
    points = cloudwatch.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName="CPUUtilization",
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=now - dt.timedelta(minutes=IDLE_MINUTES),
        EndTime=now,
        Period=300,
        Statistics=["Maximum"],
    )["Datapoints"]

    if not points:
        logger.info("%s has no CPU datapoints yet; treating as busy", instance_id)
        return True

    peak = max(p["Maximum"] for p in points)
    logger.info("%s peak CPU %.1f%% over %d minutes", instance_id, peak, IDLE_MINUTES)
    return peak >= CPU_THRESHOLD
