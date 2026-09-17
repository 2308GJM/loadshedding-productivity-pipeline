"""
Triggered when a new raw schedule file lands in S3.

Parses the EskomSePush schedule, pulls recent GitHub commit timestamps
for a configured user, computes how many coding-window hours overlapped
with load-shedding, and stores a daily summary in DynamoDB.
"""
import json
import os
import urllib.request
import boto3
from datetime import datetime, timezone

s3 = boto3.client('s3')
table = boto3.resource('dynamodb').Table(os.environ['RESULTS_TABLE'])

GITHUB_USERNAME = os.environ['GITHUB_USERNAME']
GITHUB_EVENTS_URL = f"https://api.github.com/users/{GITHUB_USERNAME}/events/public"


def get_object_from_event(event):
    record = event['Records'][0]
    bucket = record['s3']['bucket']['name']
    key = record['s3']['object']['key']
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj['Body'].read())


def fetch_recent_commit_hours():
    """Returns a set of UTC hours (0-23, today) in which a push event occurred."""
    req = urllib.request.Request(
        GITHUB_EVENTS_URL,
        headers={"Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        events = json.loads(response.read())

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    commit_hours = set()
    for e in events:
        if e.get('type') != 'PushEvent':
            continue
        created_at = e.get('created_at', '')
        if created_at.startswith(today):
            hour = int(created_at[11:13])
            commit_hours.add(hour)
    return commit_hours


def extract_outage_hours(schedule_data):
    """
    Parse EskomSePush 'events' block into a set of UTC hours affected today.
    NOTE: adjust parsing to match the actual EskomSePush response shape
    for your area/plan — this is a starting point, not final.
    """
    outage_hours = set()
    for event in schedule_data.get('events', []):
        start = event.get('start')
        end = event.get('end')
        if not start or not end:
            continue
        start_hour = int(start[11:13])
        end_hour = int(end[11:13])
        for h in range(start_hour, end_hour):
            outage_hours.add(h % 24)
    return outage_hours


def lambda_handler(event, context):
    schedule_data = get_object_from_event(event)

    outage_hours = extract_outage_hours(schedule_data)
    commit_hours = fetch_recent_commit_hours()

    lost_hours = outage_hours & commit_hours
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    table.put_item(Item={
        'date': today,
        'outage_hours': [int(h) for h in sorted(outage_hours)],
        'commit_hours': [int(h) for h in sorted(commit_hours)],
        'lost_coding_hours': [int(h) for h in sorted(lost_hours)],
        'lost_hours_count': len(lost_hours),
    })

    return {
        "statusCode": 200,
        "body": f"Processed {today}: {len(lost_hours)} coding hour(s) overlapped with load-shedding",
    }
