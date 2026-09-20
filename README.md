# Load-Shedding Productivity Pipeline

A serverless AWS pipeline that quantifies how much coding time is lost to
load-shedding, by cross-referencing real EskomSePush outage schedules with
real GitHub commit activity, and publishes the results to a public dashboard.

**Live dashboard:** http://loadshedding-dashboard-2308gjm-01.s3-website.af-south-1.amazonaws.com

## Problem

Load-shedding disrupts study and coding time unpredictably. This pipeline
turns that from a vague feeling into a measurable, trackable metric: which
hours were actually lost to outages, based on real commit activity.

## Architecture

```
EventBridge (daily) ──▶ FetchScheduleFunction ──▶ S3 (raw/YYYY-MM-DD.json)
                                                        │ (S3 trigger)
                                                        ▼
                                            ProcessDataFunction
                                              │              │
                                    (EskomSePush /schedule)  │
                                    (GitHub commit events)   │
                                                              ▼
                                                   DynamoDB (daily summaries)
                                                              │
                                                              ▼
                                          S3 static website (public dashboard)
```

- **FetchScheduleFunction** — runs daily via EventBridge, calls the
  EskomSePush `/area` endpoint (v3) for the configured area, and stores the
  raw response in S3.
- **ProcessDataFunction** — triggered automatically by the new S3 object.
  The `/area` response only lists schedule IDs, not actual outage events, so
  this function makes a follow-up call to the `/schedule` endpoint per
  auto-enabled schedule to get real outage windows. It also pulls the day's
  GitHub push events for a configured user, computes which hours overlap
  between outages and commits, writes a summary to DynamoDB, and regenerates
  the public dashboard page.
- **DynamoDB** — one item per day: outage hours, commit hours, and the
  intersection ("lost hours").
- **S3 static website** — a second, publicly readable bucket hosting a
  generated `index.html` showing the last 7 days as a table, with hours
  rendered as human-readable ranges (e.g. `13:00-15:00`) rather than raw
  counts.

## Setup

1. Install [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
   and Docker (used for `sam build --use-container`, which avoids local
   Python-version mismatches).
2. Get an [EskomSePush API token](https://sepush.co.za) and find your area
   ID via `business/3.0/areas_search?text=<suburb>`.
3. Build and deploy:
   ```bash
   sam build --use-container
   sam deploy --stack-name loadshedding-productivity-pipeline \
     --resolve-s3 --capabilities CAPABILITY_IAM \
     --parameter-overrides \
       SePushToken=<your-token> \
       SePushAreaId=<your-area-id> \
       GitHubUsername=<your-github-username> \
       BucketName=<a-globally-unique-bucket-name> \
       DashboardBucketName=<a-globally-unique-bucket-name>
   ```
4. The `DashboardURL` stack output is your public dashboard link.

## Testing

- `tests/mock_run.py` — exercises the core outage/commit overlap logic
  entirely locally, using mocked schedule and GitHub data. No AWS
  credentials or deployed resources needed.
  ```bash
  python tests/mock_run.py
  ```
- `tests/publish_mock_demo.py` — writes a clearly labeled `DEMO-<date>` row
  to the real, deployed DynamoDB table and regenerates the live dashboard,
  so the overlap logic can be demonstrated even on a day with no real
  load-shedding scheduled. Uses your real AWS credentials.
  ```bash
  python tests/publish_mock_demo.py
  ```

**Note:** as of recording the demo video, no load-shedding was scheduled for
the configured area, so a `DEMO-2026-09-20` row is present on the dashboard
to demonstrate the overlap calculation working correctly. This row is
removed before final submission via:
```bash
aws dynamodb delete-item --table-name <results-table-name> \
  --key '{"date": {"S": "DEMO-2026-09-20"}}'
```

## Design decisions

- **S3 → Lambda trigger over direct chaining** — decouples fetch and
  process steps; either can be re-run or replayed independently, and the
  process step can be triggered by any new file, not just from the fetch
  function specifically.
- **Explicit `BucketName` parameter instead of `!Ref` on the bucket
  resource** — the original design referenced the S3 bucket resource
  directly in the IAM policies of both Lambdas. Since the bucket also needed
  to invoke `ProcessDataFunction` via its event notification, this created a
  circular dependency CloudFormation couldn't resolve (bucket → function →
  bucket). Passing the bucket name in as a plain string parameter and
  building the ARN with `!Sub` breaks the cycle without losing any
  automatic wiring.
- **DynamoDB over RDS** — simple, one-item-per-day key-value summaries; no
  relational structure needed, and it's serverless (no idle cost).
  Numeric values come back from DynamoDB as `Decimal`, which required an
  explicit cast to `int` before applying Python's number formatting.
- **S3 static website hosting for the dashboard, rather than a separate
  frontend framework or CloudFront distribution** — the dashboard is a
  single generated HTML page; static hosting is the simplest way to make it
  publicly viewable without extra infrastructure.
- **GitHub push events as the coding-activity signal** — a public,
  zero-setup, zero-credential proxy for "was I actually coding at this
  hour," rather than something more invasive like screen-time tracking.
- **Local test harness kept fully separate from Lambda code** — `tests/`
  contains scripts that either run entirely locally against mocked data
  (`mock_run.py`) or write clearly-labeled demo data to the real deployed
  resources (`publish_mock_demo.py`). Neither modifies `handler.py` itself,
  so there is no demo-only branching logic in the code that actually runs
  in production.

## Known limitations

- **Hour-level granularity, not minute-level.** Overlap is computed by
  matching whole hour-of-day numbers, so a commit at 14:45 and an outage
  ending at 14:30 would still be flagged as overlapping, even though the
  outage had technically ended. This trade-off keeps the logic simple; a
  future version could compare exact timestamps instead of hour buckets.
- **GitHub commit activity is a proxy, not a direct measure**, of coding
  time — it can't detect uncommitted local work, and it only reflects
  activity on the configured public GitHub account.

## Status

Fully working end-to-end: live daily fetch, real outage-event lookup,
real GitHub commit cross-referencing, DynamoDB storage, and an
auto-updating public dashboard.

## Demo

_(link to unlisted YouTube demo video goes here)_