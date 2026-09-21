"""
Publishes a clearly-labeled demo entry to the real DynamoDB table and
regenerates the live dashboard, so the overlap logic can be shown
working end-to-end without waiting for real load-shedding to occur.

This writes to your actual deployed AWS resources — run it only when
you want the dashboard to visibly demonstrate a "lost hours" scenario.
Rerun the pipeline normally afterward (or delete the DEMO row) to
restore real data.

Usage: python tests/publish_mock_demo.py
"""
import sys
import os
import boto3


os.environ.setdefault('RESULTS_TABLE', 'loadshedding-productivity-pipeline-ResultsTable-1A2W0KKLLWGNC')
os.environ.setdefault('GITHUB_USERNAME', '2308GJM')
os.environ.setdefault('SEPUSH_TOKEN', 'unused-for-this-script')
os.environ.setdefault('DASHBOARD_BUCKET', 'loadshedding-dashboard-2308gjm-01')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'process_data'))
import handler  # reuses the real render_dashboard_html / table from production code

DEMO_DATE = "DEMO-2026-09-20"

demo_item =  [
    {
        'date': 'DEMO-2026-09-14',
        'outage_hours': [6, 7, 12, 13],
        'commit_hours': [7, 15],
        'lost_coding_hours': [7],
        'lost_hours_count': 1,
    },
    {
        'date': 'DEMO-2026-09-15',
        'outage_hours': [8, 9, 10, 16, 17],
        'commit_hours': [9, 10, 20],
        'lost_coding_hours': [9, 10],
        'lost_hours_count': 2,
    },
    {
        'date': 'DEMO-2026-09-16',
        'outage_hours': [],
        'commit_hours': [11, 15, 16],
        'lost_coding_hours': [],
        'lost_hours_count': 0,
    },
    {
        'date': 'DEMO-2026-09-17',
        'outage_hours': [12, 13, 14, 18, 19, 20],
        'commit_hours': [12, 13, 14, 19],
        'lost_coding_hours': [12, 13, 14, 19],
        'lost_hours_count': 4,
    },
    {
        'date': 'DEMO-2026-09-18',
        'outage_hours': [17, 18],
        'commit_hours': [9, 14],
        'lost_coding_hours': [],
        'lost_hours_count': 0,
    },
    {
        'date': 'DEMO-2026-09-19',
        'outage_hours': [13, 14, 18, 19],
        'commit_hours': [14, 9],
        'lost_coding_hours': [14],
        'lost_hours_count': 1,
    },
    {
    'date': DEMO_DATE,
    'outage_hours': [13, 14, 18, 19],
    'commit_hours': [14, 9],
    'lost_coding_hours': [14],
    'lost_hours_count': 1,
    },
]

for demo_item in demo_items:
    handler.table.put_item(Item=demo_item)
    print(f"Wrote demo item: {demo_item['date']} -> lost_hours_count={demo_item['lost_hours_count']}")

handler.publish_dashboard()
print("Dashboard refreshed with demo entry.")