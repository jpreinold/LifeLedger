import argparse
import json
import re
import urllib.error
import urllib.request
from urllib.parse import urljoin


REQUIRED_ALARMS = {
    "ReconciliationFunctionErrorAlarm",
    "RequiresAttentionAlarm",
    "OldUnresolvedReconciliationAlarm",
    "DocumentScanningBacklogAlarm",
    "AccountDeletionIncompleteAlarm",
    "AccountOperationsDeadLetterAlarm",
    "ProductionE2ERepeatedFailureAlarm",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a deployed LifeLedger production stack without printing secrets.")
    parser.add_argument("--stack-name", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--expected-frontend-api")
    parser.add_argument("--expected-origin", default="https://lifeledger.jpreinold.com")
    parser.add_argument("--frontend-url", default="https://lifeledger.jpreinold.com")
    args = parser.parse_args()

    import boto3

    cloudformation = boto3.client("cloudformation", region_name=args.region)
    stack = cloudformation.describe_stacks(StackName=args.stack_name)["Stacks"][0]
    if not stack["StackStatus"].endswith("COMPLETE"):
        raise RuntimeError(f"Stack status is not complete: {stack['StackStatus']}")
    outputs = {item["OutputKey"]: item["OutputValue"] for item in stack.get("Outputs", [])}
    api_url = outputs["ApiUrl"].rstrip("/")
    _expect_json(f"{api_url}/health", 200, {"status": "ok"})
    version = _request_json(f"{api_url}/version", expected_status=200)
    if version.get("environment") != "production" or version.get("git_commit") != args.expected_commit:
        raise RuntimeError("Version endpoint does not match the expected production commit.")
    _request_json(f"{api_url}/records", expected_status=401)
    _expect_cors(f"{api_url}/records", args.expected_origin)
    if args.expected_frontend_api and args.expected_frontend_api.rstrip("/") != api_url:
        raise RuntimeError("The expected frontend API URL does not match the deployed API output.")
    _verify_frontend_api(args.frontend_url, api_url)

    s3 = boto3.client("s3", region_name=args.region)
    for output in ("DocumentsQuarantineBucketName", "DocumentsCleanBucketName", "AccountExportsBucketName"):
        bucket = outputs[output]
        block = s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"]
        if not all(block.get(key) for key in ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")):
            raise RuntimeError(f"Public access block is incomplete for {output}.")
        rules = s3.get_bucket_encryption(Bucket=bucket)["ServerSideEncryptionConfiguration"]["Rules"]
        if rules[0]["ApplyServerSideEncryptionByDefault"].get("SSEAlgorithm") != "aws:kms":
            raise RuntimeError(f"KMS encryption is not active for {output}.")

    dynamodb = boto3.client("dynamodb", region_name=args.region)
    for output in ("ResponsibilityHistoryTableName", "ReconciliationTableName", "AccountOperationsTableName"):
        if dynamodb.describe_table(TableName=outputs[output])["Table"]["TableStatus"] != "ACTIVE":
            raise RuntimeError(f"{output} is not active.")

    events = boto3.client("events", region_name=args.region)
    rules = events.list_rule_names_by_target(TargetArn=_function_arn(args, outputs["ReconciliationFunctionName"]))
    if len(rules.get("RuleNames", [])) < 3:
        raise RuntimeError("The retry, artifact-cleanup, and deep reconciliation schedules were not all found.")

    resources = []
    paginator = cloudformation.get_paginator("list_stack_resources")
    for page in paginator.paginate(StackName=args.stack_name):
        resources.extend(page["StackResourceSummaries"])
    alarm_ids = {item["LogicalResourceId"] for item in resources if item["ResourceType"] == "AWS::CloudWatch::Alarm"}
    missing = REQUIRED_ALARMS - alarm_ids
    if missing:
        raise RuntimeError("Missing required alarms: " + ", ".join(sorted(missing)))

    print(json.dumps({"event": "deployment_verification_result", "status": "success", "environment": "production", "app_version": version.get("app_version"), "git_commit": version.get("git_commit")}, indent=2))
    return 0


def _function_arn(args, function_name):
    import boto3

    return boto3.client("lambda", region_name=args.region).get_function(FunctionName=function_name)["Configuration"]["FunctionArn"]


def _request_json(url, expected_status):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status = response.status
            body = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        body = error.read()
    if status != expected_status:
        raise RuntimeError(f"Unexpected HTTP status for deployment check: expected {expected_status}, received {status}.")
    return json.loads(body or b"{}")


def _expect_cors(url, origin):
    request = urllib.request.Request(
        url,
        method="OPTIONS",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-correlation-id",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status = response.status
            allowed_origin = response.headers.get("Access-Control-Allow-Origin")
    except urllib.error.HTTPError as error:
        status = error.code
        allowed_origin = error.headers.get("Access-Control-Allow-Origin")
    if status not in {200, 204} or allowed_origin != origin:
        raise RuntimeError("Production CORS verification failed for the expected allowlisted origin.")


def _expect_json(url, expected_status, expected_body):
    if _request_json(url, expected_status) != expected_body:
        raise RuntimeError("Deployment health response was unexpected.")


def _verify_frontend_api(frontend_url, api_url):
    base = frontend_url.rstrip("/") + "/"
    html = _request_text(base)
    candidates = [urljoin(base, path) for path in re.findall(r'["\']([^"\']+\.js)["\']', html)]
    visited = set()
    total_bytes = 0
    while candidates and len(visited) < 20 and total_bytes < 5_000_000:
        url = candidates.pop(0)
        if url in visited:
            continue
        visited.add(url)
        source = _request_text(url)
        total_bytes += len(source.encode("utf-8"))
        if api_url in source:
            return
        candidates.extend(
            urljoin(url, path)
            for path in re.findall(r'["\']([^"\']+\.js)["\']', source)
            if urljoin(url, path) not in visited
        )
    raise RuntimeError("The deployed frontend bundle does not reference the expected API URL.")


def _request_text(url):
    request = urllib.request.Request(url, headers={"Accept": "text/html,application/javascript"})
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError("Frontend deployment verification returned an unexpected status.")
        return response.read().decode("utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
