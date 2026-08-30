import sys, os, json; sys.path.insert(0, "/tmp/claude-1000/-home-abad-naseer-Downloads-shanipracha/2ce18451-7755-427a-9d35-e76bf277e4cc/scratchpad")
import awsenv; awsenv.load()
import boto3

HERE = os.path.dirname(__file__)
ec2 = boto3.client("ec2", region_name="us-west-2")

# g6.xlarge is what this is for. Two things stop it today, and only the account
# owner can clear either:
#
#   1. The account is on the AWS Free Tier plan, so RunInstances refuses any
#      type that is not free tier eligible. No GPU type is.
#   2. The "Running On-Demand G and VT instances" quota is 0. A request for 4
#      vCPUs is submitted and pending.
#
# So the same build runs on the largest free tier box instead: 2 vCPU and 8 GB,
# enough for llama3.1:8b on CPU. Everything except the speed is identical, the
# same AMI, security group, install, auto off, and the same address the
# applications call. Once both are cleared this is a stop, a type change and a
# start, not a rebuild.
INSTANCE_TYPE = "m7i-flex.large"

user_data = open(os.path.join(HERE, "userdata.sh")).read()

out = ec2.run_instances(
    ImageId="ami-0ba3fae0cca9442ee",
    InstanceType=INSTANCE_TYPE,
    MinCount=1, MaxCount=1,
    KeyName="ollama-gpu",
    SecurityGroupIds=["sg-06ad9397831595b43"],
    UserData=user_data,
    # `shutdown -h` from the idle timer therefore stops the machine rather than
    # destroying it. This is what makes the auto off need no IAM at all.
    InstanceInitiatedShutdownBehavior="stop",
    BlockDeviceMappings=[{
        "DeviceName": "/dev/sda1",
        "Ebs": {"VolumeSize": 40, "VolumeType": "gp3", "DeleteOnTermination": True},
    }],
    TagSpecifications=[{
        "ResourceType": "instance",
        "Tags": [
            {"Key": "Name", "Value": "smartzees-ollama"},
            {"Key": "Purpose", "Value": "Own model for the three SmartZees agents"},
            {"Key": "PendingResize", "Value": "g6.xlarge once the G quota is granted"},
        ],
    }],
)
inst = out["Instances"][0]
print(json.dumps({"instance_id": inst["InstanceId"], "type": inst["InstanceType"]}))
