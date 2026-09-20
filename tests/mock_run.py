"""
Local test harness for process_data — exercises the real outage/commit
overlap logic against mocked EskomSePush and GitHub responses, without
touching AWS or the deployed Lambda.

Run with: python tests/mock_run.py
"""
import sys
import os
import json
from unittest import mock
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'process_data'))

TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')

MOCK_AREA_DATA = {
    "schedules": [{"id": "eskde-10", "type": "loadshedding", "auto_enabled": True}]
}

MOCK_SCHEDULE_EVENTS = {
    "events": [
        {"start": f"{TODAY}T13:00:00+00:00", "end": f"{TODAY}T15:00:00+00:00"},
        {"start": f"{TODAY}T18:00:00+00:00", "end": f"{TODAY}T20:00:00+00:00"},
    ]
}

MOCK_GITHUB_EVENTS = [
    {"type": "PushEvent", "created_at": f"{TODAY}T14:10:00Z"},
    {"type": "PushEvent", "created_at": f"{TODAY}T09:00:00Z"},
]

os.environ.setdefault('RESULTS_TABLE', 'mock-table')
os.environ.setdefault('GITHUB_USERNAME', 'mock-user')
os.environ.setdefault('SEPUSH_TOKEN', 'mock-token')
os.environ.setdefault('DASHBOARD_BUCKET', 'mock-bucket')

with mock.patch('boto3.resource'), mock.patch('boto3.client'):
    import handler


def run():
    with mock.patch.object(handler, 'fetch_schedule_events', return_value=MOCK_SCHEDULE_EVENTS):
        outage_hours = handler.extract_outage_hours(MOCK_AREA_DATA)

    with mock.patch('json.loads', return_value=MOCK_GITHUB_EVENTS):
        with mock.patch('urllib.request.urlopen'):
            commit_hours = set()
            for e in MOCK_GITHUB_EVENTS:
                if e['type'] == 'PushEvent' and e['created_at'].startswith(TODAY):
                    commit_hours.add(int(e['created_at'][11:13]))

    lost_hours = outage_hours & commit_hours

    print(f"Outage hours:      {handler.format_hour_list(outage_hours)}")
    print(f"Commit hours:      {handler.format_hour_list(commit_hours)}")
    print(f"Lost coding hours: {handler.format_hour_list(lost_hours)}")
    print(f"Lost hours count:  {len(lost_hours)}")


if __name__ == '__main__':
    run()