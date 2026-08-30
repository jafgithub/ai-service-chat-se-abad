import sys; sys.path.insert(0, "/tmp/claude-1000/-home-abad-naseer-Downloads-shanipracha/2ce18451-7755-427a-9d35-e76bf277e4cc/scratchpad")
import awsenv; awsenv.load()
import boto3, botocore

REGIONS = ["us-west-2", "us-east-1", "ap-southeast-1"]

def try_call(label, fn):
    try:
        return fn()
    except botocore.exceptions.ClientError as e:
        print(f"  {label}: DENIED/ERROR {e.response['Error']['Code']}")
        return None
    except Exception as e:
        print(f"  {label}: {type(e).__name__}")
        return None

for region in REGIONS:
    print(f"\n=== {region} ===")
    ec2 = boto3.client("ec2", region_name=region)

    # The quota that decides whether a G instance can exist at all.
    sq = boto3.client("service-quotas", region_name=region)
    q = try_call("quota", lambda: sq.get_service_quota(ServiceCode="ec2", QuotaCode="L-DB2E81BA"))
    if q:
        print(f"  Running On-Demand G and VT vCPUs : {q['Quota']['Value']:.0f}")

    ins = try_call("instances", lambda: ec2.describe_instances())
    if ins is not None:
        n = sum(len(r["Instances"]) for r in ins["Reservations"])
        print(f"  existing instances               : {n}")
        for r in ins["Reservations"]:
            for i in r["Instances"]:
                if i["State"]["Name"] != "terminated":
                    print(f"    {i['InstanceId']} {i['InstanceType']} {i['State']['Name']} {i.get('PublicIpAddress','')}")

    vpcs = try_call("vpcs", lambda: ec2.describe_vpcs())
    if vpcs is not None:
        for v in vpcs["Vpcs"]:
            print(f"  vpc {v['VpcId']} {v['CidrBlock']} default={v.get('IsDefault')}")

    kp = try_call("keypairs", lambda: ec2.describe_key_pairs())
    if kp is not None:
        print(f"  key pairs                        : {[k['KeyName'] for k in kp['KeyPairs']] or 'none'}")
