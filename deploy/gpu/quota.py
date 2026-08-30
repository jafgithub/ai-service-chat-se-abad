import sys; sys.path.insert(0, "/tmp/claude-1000/-home-abad-naseer-Downloads-shanipracha/2ce18451-7755-427a-9d35-e76bf277e4cc/scratchpad")
import awsenv; awsenv.load()
import boto3, botocore

sq = boto3.client("service-quotas", region_name="us-west-2")

print("=== any request already in flight? ===")
try:
    hist = sq.list_requested_service_quota_change_history_by_quota(
        ServiceCode="ec2", QuotaCode="L-DB2E81BA")
    reqs = hist.get("RequestedQuotas", [])
    if not reqs:
        print("  none")
    for r in reqs:
        print(f"  {r['Id']} desired={r['DesiredValue']:.0f} status={r['Status']} {r.get('Created')}")
except botocore.exceptions.ClientError as e:
    print("  cannot read history:", e.response["Error"]["Code"])

print("=== can this user request an increase? ===")
try:
    out = sq.request_service_quota_increase(
        ServiceCode="ec2", QuotaCode="L-DB2E81BA", DesiredValue=4.0)
    r = out["RequestedQuota"]
    print(f"  SUBMITTED id={r['Id']} desired={r['DesiredValue']:.0f} status={r['Status']}")
except botocore.exceptions.ClientError as e:
    code = e.response["Error"]["Code"]
    print(f"  {code}: {e.response['Error']['Message'][:200]}")
