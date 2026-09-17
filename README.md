# Load-Shedding Productivity Pipeline

A serverless AWS pipeline that quantifies how much coding time is lost to
load-shedding, by cross-referencing EskomSePush schedule data with real
GitHub commit activity.

## Problem

Load-shedding disrupts study and coding time unpredictably. This pipeline
turns that into a measurable, trackable metric instead of a vague feeling.

## Architecture

```
EventBridge (daily) → Lambda: fetch_schedule → S3 (raw/YYYY-MM-DD.json)
                                                    │ (S3 trigger)
                                                    ▼
                                          Lambda: process_data
                                                    │
                                                    ▼
                                          DynamoDB (daily summaries)
```

- **fetch_schedule** — pulls the day's load-shedding schedule from the
  EskomSePush API and stores the raw response in S3.
- **process_data** — triggered by the new S3 object; parses outage
  windows, pulls recent GitHub push-event timestamps, and computes the
  overlap between outage hours and coding hours.
- **DynamoDB** — stores one summary item per day: outage hours, commit
  hours, and the hours lost to overlap.

## Setup

1. Install [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html).
2. Get an [EskomSePush API token](https://sepush.co.za) and your area ID.
3. Deploy:
   ```bash
   sam build
   sam deploy --guided
   ```
   You'll be prompted for `SePushToken`, `SePushAreaId`, and `GitHubUsername`.

## Design decisions

- **S3 → Lambda trigger over direct chaining** — decouples fetch and
  process steps, makes each independently testable and replayable.
- **DynamoDB over RDS** — simple daily key-value summaries, no relational
  needs, and it's serverless (no idle cost).
- **EventBridge schedule over polling** — the fetch only needs to run
  once a day; no need for a long-running process.

## Status

Early scaffold — see commit history for progress.

## Demo

_(link to unlisted YouTube demo video goes here)_
