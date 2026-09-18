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
SEPUSH_TOKEN = os.environ.get('SEPUSH_TOKEN')

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


def fetch_schedule_events(schedule_id):
    """Fetch actual outage events for a given schedule ID (e.g. 'eskde-10')."""
    url = f"https://developer.sepush.co.za/business/3.0/schedule?id={schedule_id}"
    req = urllib.request.Request(url, headers={"Token": SEPUSH_TOKEN})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read())

def extract_outage_hours(schedule_data):
    """
    area_data is the raw /area response (schedules list only, no events).
    For each auto-enabled schedule, fetch its actual events and collect
    the affected hours for today.
    """
    outage_hours = set()
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    for sched in area_data.get('schedules', []):
        if not sched.get('auto_enabled'):
            continue
        schedule_id = sched['id']
        schedule_data = fetch_schedule_events(schedule_id)

        for event in schedule_data.get('events', []):
            start = event.get('start')
            end = event.get('end')
            if not start or not (start.startswith(today)):
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
