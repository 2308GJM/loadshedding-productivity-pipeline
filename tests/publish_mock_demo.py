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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'process_data'))
import handler  # reuses the real render_dashboard_html / table from production code

DEMO_DATE = "DEMO-2026-09-20"

demo_item = {
    'date': DEMO_DATE,
    'outage_hours': [13, 14, 18, 19],
    'commit_hours': [14, 9],
    'lost_coding_hours': [14],
    'lost_hours_count': 1,
}

handler.table.put_item(Item=demo_item)
print(f"Wrote demo item: {demo_item}")

handler.publish_dashboard()
print("Dashboard refreshed with demo entry.")