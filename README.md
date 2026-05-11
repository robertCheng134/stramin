# Stramin

Stramin is an adaptive recovery operating system for training decisions.

It is Garmin-first, automation-first, and reliability-first. The goal is not to
produce motivational text. The goal is to safely decide whether today is a day
to train, go light, recover, or rest based on validated health data.

## What Is Stramin?

Stramin turns finalized Garmin recovery signals into daily training guidance.
It treats recovery data as operational infrastructure: data must be present,
fresh enough, validated, and delivered through a dependable workflow before it
becomes a recommendation.

Product identity:

- adaptive recovery platform
- Garmin-first health automation
- rule-based daily recommendation engine
- Telegram delivery layer
- local-first operational system for private health data

Garmin is the source of truth for v4. Strava, GPT, CSV, and manual entry are
supporting paths, not the core production path.

## Why It Exists

Most training decisions are reactive. People look at how they feel after
training has already gone sideways. Recovery signals exist, but they are often
ignored, scattered across apps, or unavailable at the exact moment a decision is
needed.

Health platforms are also operationally fragile:

- Garmin finalized sleep, HRV, and recovery data can lag into the morning.
- Local sync/import tools can fail or produce stale-looking rows.
- Raw health database tables may not be ordered the way humans expect.
- Automated notifications are risky if they send before validation passes.

Stramin exists because automation reliability matters. A training
recommendation should not be sent just because a cron job fired. It should be
sent only when the health data is ready.

## Core System Philosophy

- **Validation-first:** no validated data, no training recommendation.
- **Graceful degradation:** if data is not ready, retry or warn instead of
  pretending.
- **Garmin as source of truth:** v4 production recommendations are anchored on
  GarminDB finalized health data.
- **Rule-based reliability before AI autonomy:** deterministic safety comes
  before narrative intelligence.
- **Infrastructure-first v4:** sync, validation, retries, duplicate prevention,
  logs, and Telegram delivery are the product surface.

AI is deliberately optional. Stramin should remain useful when GPT is missing,
disabled, or unavailable.

## Operational Architecture

```text
Garmin Connect
      |
      v
GarminDB local SQLite
      |
      v
Validation gate
      |
      v
Recovery analysis
      |
      v
Recommendation generation
      |
      v
Telegram delivery
      |
      v
Retry and duplicate prevention
```

The production path is intentionally boring: local files, explicit validation,
synchronous scripts, atomic state, and plain logs.

## Production Reliability Features

- stale-data detection
- Garmin finalized-data lag handling
- retry architecture for morning readiness
- duplicate Telegram report prevention
- dry-run safety
- atomic `daily_state.json` generation
- `data/notification_state.json` publish tracking
- graceful fallback behavior
- clear failure logging

Garmin finalized recovery data can be yesterday. That is normal and accepted by
v4 validation. Data older than yesterday is treated as too stale for automatic
recommendations.

## Current Platform Capabilities

- GarminDB ingestion from local SQLite databases
- recovery score and recovery level analysis
- adaptive daily recommendation
- Telegram daily report publishing
- automation pipeline with retry-aware readiness handling
- duplicate-send protection
- dry-run Telegram preview
- weekly planning and dynamic adaptation foundations
- optional Strava training-load context
- optional GPT explanation layer

## GarminDB Production Notes

Stramin reads GarminDB from local SQLite files, usually:

```text
~/HealthData/DBs/garmin.db
~/HealthData/DBs/garmin_monitoring.db
```

GarminDB credentials do not live in Stramin. They belong in:

```text
~/.GarminDb/GarminConnectConfig.json
```

Important production rule: do not order GarminDB health tables by `rowid`.
After bulk import/analyze, `rowid` does not represent chronological order.
Always order by business date columns:

- `hrv.day`
- `sleep.day`
- `daily_summary.day`

See [GarminDB operations](docs/garmindb-operations.md) for sync commands,
validation queries, and known GarminDB issues.

## AI Philosophy

AI is optional augmentation, not the control plane.

v4 keeps recommendation safety deterministic. GPT may explain a recommendation
when available, but it must not replace validation, freshness checks, recovery
rules, or decision engine semantics.

v5 is reserved for orchestration, richer coaching, and safer personalization.
That work is intentionally postponed until the operational foundation is boring
enough to trust.

## Developer Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 -m pytest
```

Useful local checks:

```bash
python3 scripts/test_garmindb_today.py --db-dir ~/HealthData/DBs --debug
python3 scripts/preview_garmindb_recommendation.py --db-dir ~/HealthData/DBs
python3 automation/run_daily_pipeline.py --db-dir ~/HealthData/DBs --dry-run
```

Run the real Telegram publish path only after dry-run output looks correct:

```bash
python3 automation/run_daily_pipeline.py --db-dir ~/HealthData/DBs
```

## Environment

Common `.env` values:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
GARMINDB_PATH=/home/rc/HealthData/DBs/garmin.db
GARMINDB_DIR=/home/rc/HealthData/DBs
STRAVA_ACCESS_TOKEN=your_token_here
OPENAI_API_KEY=your_key_here
```

Automation timing:

```env
STRAMIN_DAILY_REPORT_TIME=09:00
STRAMIN_RETRY_INTERVAL_MINUTES=5
STRAMIN_RETRY_CUTOFF_TIME=11:00
```

`.env` is ignored and must never be committed.

## Repository Structure

```text
automation/                  v4 pipeline, validation, state generation
docs/                        operational design and GarminDB runbooks
reports/                     Telegram report formatting
scripts/                     GarminDB inspection and preview tools
src/integrations/            GarminDB, Telegram, CSV, and future adapters
src/recovery_rules.py        recovery score and level
src/decision_engine.py       daily training decision
src/weekly_planner.py        weekly planning and adaptation
src/telegram_bot.py          Telegram command interface
tests/                       unit and integration tests
```

Module references:

- `automation/validate_health_data.py`: production freshness gate
- `automation/build_daily_state.py`: atomic daily state generation
- `automation/run_daily_pipeline.py`: retry-aware publish pipeline
- `src/integrations/garmindb.py`: GarminDB ingestion and metric metadata
- `src/integrations/telegram_sender.py`: safe Telegram send abstraction
- `reports/telegram_report.py`: user-facing Telegram message format

## Testing

Run all tests:

```bash
python3 -m pytest
```

Tests must not require real Garmin credentials, real health databases, or real
Telegram network calls. GarminDB tests use temporary SQLite databases.

## Deployment Notes

Use `tmux` for long-running sync and bot processes:

```bash
tmux new -s stramin-sync
cd ~/stramin
source .venv/bin/activate
garmindb_cli.py --all --download --import --analyze --latest
```

Detach with `Ctrl-b d`; reattach with:

```bash
tmux attach -t stramin-sync
```

Do not hide GarminDB sync failures behind silent automation. v4 favors visible
operator control until sync behavior is stable enough for cron/systemd.

## Privacy And Security

Never commit:

- `.env`
- `.venv/`
- `HealthData/`
- `logs/`
- `*.db`
- `*.sqlite`
- `*.log`
- Garmin credentials
- real `data/garmin_health.csv`

Health data, Telegram IDs, GarminDB files, and logs are private runtime
artifacts.

## Historical And Deprecated Workflows

These workflows remain useful for development, fallback, and tests, but they
are no longer the primary v4 production path.

CSV/manual Garmin flow:

```bash
python3 src/add_garmin_entry.py
python3 src/morning_check.py
python3 src/main.py
```

Sample CSV data lives at:

```text
data/garmin_health_sample.csv
```

Real CSV health data should remain local and ignored:

```text
data/garmin_health.csv
```

## Roadmap

v4:

- production-safe GarminDB ingestion
- validation-gated Telegram delivery
- retry and duplicate prevention
- operational logging
- stale-data protection
- deployment hygiene

v5:

- AI orchestration layer
- richer coaching narratives
- training-history-aware adaptation
- safer personalization controls
- multi-source health intelligence
