import sys, os, json; sys.path.insert(0, "/tmp/claude-1000/-home-abad-naseer-Downloads-shanipracha/2ce18451-7755-427a-9d35-e76bf277e4cc/scratchpad")
import awsenv; awsenv.load()
import boto3, botocore

REGION = "us-west-2"
ec2 = boto3.client("ec2", region_name=REGION)

MYIP = open(os.path.join(os.path.dirname(__file__), "myip")).read().strip()

# The only three machines that may ever speak to the model. Ollama has no
# authentication of any kind: anything that reaches this port can use the
# model, read every prompt, and pull or delete models. So it is never
# 0.0.0.0/0, and these are /32.
APP_BOXES = [
    ("35.91.251.211/32", "SmartService"),
    ("54.188.207.85/32", "SmartCommunity"),
    ("54.254.25.0/32",   "SmartMarket"),
]

def existing_sg():
    try:
        out = ec2.describe_security_groups(Filters=[{"Name": "group-name", "Values": ["ollama-gpu"]}])
        return out["SecurityGroups"][0]["GroupId"] if out["SecurityGroups"] else None
    except botocore.exceptions.ClientError:
        return None

sg = existing_sg()
if sg:
    print(f"  security group already there: {sg}")
else:
    vpc = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"][0]["VpcId"]
    sg = ec2.create_security_group(
        GroupName="ollama-gpu",
        Description="Ollama for the SmartZees agents. 11434 to the three app boxes only.",
        VpcId=vpc,
    )["GroupId"]
    print(f"  created security group {sg} in {vpc}")

    ec2.authorize_security_group_ingress(GroupId=sg, IpPermissions=[
        {
            "IpProtocol": "tcp", "FromPort": 11434, "ToPort": 11434,
            "IpRanges": [{"CidrIp": cidr, "Description": f"{name} may ask the model"}
                         for cidr, name in APP_BOXES],
        },
        {
            "IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
            "IpRanges": [{"CidrIp": f"{MYIP}/32", "Description": "Abad, for setup"}],
        },
    ])
    print("  rules: 11434 from the three app boxes, 22 from this machine, nothing else")

# A key pair, so there is a way in if the unattended install goes wrong.
key_path = os.path.join(os.path.dirname(__file__), "ollama-gpu.pem")
try:
    ec2.describe_key_pairs(KeyNames=["ollama-gpu"])
    print("  key pair already there")
except botocore.exceptions.ClientError:
    kp = ec2.create_key_pair(KeyName="ollama-gpu", KeyType="ed25519")
    with open(key_path, "w") as f:
        f.write(kp["KeyMaterial"])
    os.chmod(key_path, 0o600)
    print(f"  created key pair, private key written to {key_path}")

print(json.dumps({"sg": sg, "region": REGION}))
