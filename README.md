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

## Prerequisites

- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- [Docker Desktop](https://www.docker.com/products/docker-desktop) (used for
  `sam build --use-container`, which avoids local Python-version mismatches)
- An AWS account with an IAM user that has deploy permissions, configured via:
```bash
  aws configure
```
- An [EskomSePush API token](https://sepush.co.za)
- Your EskomSePush area ID — find it with:
```bash
  curl.exe -H "Token: YOUR_TOKEN" "https://developer.sepush.co.za/business/3.0/areas_search?text=<your-suburb>"
```
Pick the `id` field matching your actual suburb from the returned list.

## Deploying

1. Build (inside a container, to avoid local Python version mismatches):
```bash
   sam build --use-container
```

2. Deploy, passing your own values:
```bash
   sam deploy \
     --stack-name loadshedding-productivity-pipeline \
     --resolve-s3 \
     --capabilities CAPABILITY_IAM \
     --parameter-overrides \
       SePushToken=<your-eskomsepush-token> \
       SePushAreaId=<your-area-id> \
       GitHubUsername=<your-github-username> \
       BucketName=<a-globally-unique-bucket-name> \
       DashboardBucketName=<a-different-globally-unique-bucket-name>
```
Bucket names must be globally unique across all of AWS, not just your
account, append your username or a random suffix if a name is taken.

3. Grab the dashboard URL from the deploy output, or fetch it any time with:
```bash
   aws cloudformation describe-stacks \
     --stack-name loadshedding-productivity-pipeline \
     --query "Stacks[0].Outputs" --output table
```

## Running / verifying it manually

The pipeline runs automatically once a day via EventBridge, but you can
trigger it manually to see it work immediately:

```bash
# Find your actual deployed function names
aws lambda list-functions --query "Functions[].FunctionName" --output table

# Trigger the fetch function
aws lambda invoke --function-name <FetchScheduleFunction-name> output.json
cat output.json
```

Check that the raw file landed in S3:
```bash
aws s3 ls s3://<your-bucket-name>/raw/
```

Check that the process function ran (triggered automatically by the S3
upload above) and wrote a summary:
```bash
aws dynamodb scan --table-name <your-ResultsTable-name>
```

Check the process function's logs if something looks off:
```bash
aws logs tail /aws/lambda/<ProcessDataFunction-name> --since 10m
```

Then open the dashboard URL in a browser to see the updated table and chart.

## Testing

**Local logic test — no AWS required:**
```bash
python tests/mock_run.py
```
Runs the outage/commit overlap calculation against mocked data entirely
offline, to verify the core logic in isolation.

**Live demo data — writes to your real, deployed dashboard:**
```bash
python tests/publish_mock_demo.py
```
Writes several clearly-labeled `DEMO-<date>` rows to the real DynamoDB table
and regenerates the live dashboard, so the overlap logic and chart can be
demonstrated even on a day with no real load-shedding scheduled. This uses
your real AWS credentials and writes to your real deployed resources.

**To remove demo data before final submission:**
```bash
aws dynamodb delete-item --table-name <your-ResultsTable-name> \
  --key '{"date": {"S": "DEMO-2026-09-14"}}'
# repeat for each DEMO-<date> row you added
```
Then trigger the fetch function once more (see above) to regenerate a clean
dashboard with only real data.

## Changing configuration later

Every parameter is a deploy-time value, not hardcoded, so you can update any
of them by redeploying with new `--parameter-overrides` — for example, to
change area:
```bash
sam deploy --stack-name loadshedding-productivity-pipeline \
  --resolve-s3 --capabilities CAPABILITY_IAM \
  --parameter-overrides SePushAreaId=<new-area-id>
```
(Omit parameters you don't want to change — SAM keeps their previous values
if you've saved them to `samconfig.toml`, or pass all of them again if not.)

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
  time as it can't detect uncommitted local work, and it only reflects
  activity on the configured public GitHub account.

## Real-world extension beyond personal use

The same pattern that fetches external outage data, cross-reference it against an
internal activity signal, surface the overlap and generalizes beyond tracking
personal coding time:
- A small business could swap GitHub commits for point-of-sale transaction
  timestamps, to quantify exactly how much trading time and revenue is lost
  to outages each week.
- A call center could cross-reference outage windows against ticket volume
  to quantify service disruption.
- A logistics operation could tie it to dispatch timestamps to measure
  delivery delays caused by outages.

Only the second data source changes is the architecture stays the same

## Status

Fully working end-to-end: live daily fetch, real outage-event lookup,
real GitHub commit cross-referencing, DynamoDB storage, and an
auto-updating public dashboard.

## Repo Verification Code

WTC-ABG34SFE


## Demo

https://youtu.be/g5TsP4wGA_k?si=3LRmXnDQQ8dYIk17