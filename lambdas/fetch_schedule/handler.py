"""
Fetches the load-shedding schedule for a configured area from the
EskomSePush API and writes the raw response to S3.

Triggered daily via EventBridge (see template.yaml).
"""
import json
import os
import urllib.request
import boto3
from datetime import datetime, timezone

s3 = boto3.client('s3')

BUCKET = os.environ['BUCKET_NAME']
SEPUSH_TOKEN = os.environ['SEPUSH_TOKEN']
SEPUSH_AREA_ID = os.environ['SEPUSH_AREA_ID']

SEPUSH_URL = f"https://developer.sepush.co.za/business/2.0/area?id={SEPUSH_AREA_ID}"


def fetch_schedule():
    req = urllib.request.Request(SEPUSH_URL, headers={"Token": SEPUSH_TOKEN})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read())


def lambda_handler(event, context):
    data = fetch_schedule()

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    key = f"raw/{today}.json"

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(data),
        ContentType="application/json",
    )

    return {"statusCode": 200, "body": f"Saved {key} to {BUCKET}"}
