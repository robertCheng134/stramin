# AGENTS.md

Guidance for AI coding agents and contributors working on Stramin.

## Mission

Stramin provides reliable Garmin-first recovery and training recommendations
from local health data. The project values operational transparency, privacy,
and stable rule-based behavior over clever automation.

## Current Status

- Branch focus: `feature/garmindb-today-flow`
- Release track: v4 infrastructure
- v4 priority: data ingestion, validation, Telegram delivery, deployment, logs
- v5 direction: AI coaching and richer personalization

Do not add AI coaching features in v4.

## Architecture

```text
GarminDB / CSV / Manual entry
        |
        v
HealthData
        |
        +--> recovery_rules.py
        +--> decision_engine.py
        +--> weekly_planner.py
        |
        +--> CLI previews
        +--> Telegram bot
```

Server responsibilities:

- run GarminDB sync/import jobs
- store `~/HealthData`
- run Telegram bot
- validate data before publishing recommendations

Client/developer responsibilities:

- edit code
- run tests
- push focused branches
- keep private data out of git

## Coding Philosophy

- reliability > cleverness
- explicit/simple code > abstraction-heavy code
- operational transparency > automation magic
- preserve existing behavior unless the task explicitly asks to change it
- add tests for every meaningful ingestion, formatting, or fallback change

Good example:

```python
if stress < 0:
    skip_invalid_row()
```

Less good:

```python
normalize_all_metrics_with_hidden_magic()
```

## Forbidden Changes

Do not:

- redesign `recovery_rules.py`
- redesign `decision_engine.py`
- redesign `weekly_planner.py`
- redesign HRV semantics without explicit instruction
- remove tests
- introduce fake AI coaching logic
- auto-run GarminDB sync/download/import from Telegram
- commit private data, DBs, logs, `.env`, or credentials

Acceptable refactor scope:

- local helper extraction
- clearer metadata
- safer fallback handling
- docs/tests/scripts that improve operations
- ingestion-layer changes with tests

## Testing Expectations

Run:

```bash
python3 -m pytest
```

For GarminDB work, also run:

```bash
python3 scripts/test_garmindb_today.py --db-dir ~/HealthData/DBs --debug
python3 scripts/preview_garmindb_recommendation.py --db-dir ~/HealthData/DBs
```

Tests must not require real Garmin credentials or real Telegram network calls.
Use temporary SQLite databases for GarminDB integration tests.

## Branch Workflow

- Use feature branches.
- Keep commits focused and reviewable.
- Do not mix product logic, infra docs, and unrelated refactors in one change.
- Before handoff, report changed files and test results.

## Deployment Philosophy

Deployment should be boring and inspectable:

- run long jobs in `tmux`
- validate DB tables before Telegram push
- write logs to `logs/`
- generate daily state atomically
- skip publish on stale or invalid data
- fail loudly in logs, gently in user-facing output

## GarminDB Operational Notes

Paths:

- config: `~/.GarminDb/GarminConnectConfig.json`
- health root: `~/HealthData`
- main DB: `~/HealthData/DBs/garmin.db`
- monitoring DB: `~/HealthData/DBs/garmin_monitoring.db`
- Stramin virtualenv: `~/stramin/.venv`

Preferred sync command:

```bash
garmindb_cli.py --all --download --import --analyze --latest
```

Known instability:

```text
garmindb_cli.py --download
TypeError: argument of type 'NoneType' is not iterable
```

Use `tmux` for sync jobs. Do not hide GarminDB failures behind silent retries.

Raw table ordering rule:

- GarminDB raw tables `hrv` and `sleep` are usable.
- Do not order GarminDB health tables by `rowid`.
- `rowid` does not represent chronological order after bulk import/analyze.
- Always order by the business date column:
  - `hrv.day`
  - `sleep.day`
  - `daily_summary.day`

Verified latest-data query examples:

```bash
sqlite3 ~/HealthData/DBs/garmin.db "select day, last_night_avg, status from hrv order by day desc limit 1;"
sqlite3 ~/HealthData/DBs/garmin.db "select day, total_sleep from sleep order by day desc limit 1;"
sqlite3 ~/HealthData/DBs/garmin.db "select day, rhr, stress_avg, bb_charged from daily_summary order by day desc limit 1;"
```

Latest finalized Garmin recovery data can be yesterday. This is normal and is
accepted by v4 validation; older data should be treated as too stale for
automatic recommendations.

## tmux Workflow

```bash
tmux new -s stramin-sync
source ~/stramin/.venv/bin/activate
garmindb_cli.py --all --download --import --analyze --latest
```

Detach:

```text
Ctrl-b d
```

Reattach:

```bash
tmux attach -t stramin-sync
```

## Data Privacy Rules

Never commit:

- `.env`
- `.venv/`
- `HealthData/`
- `logs/`
- `*.db`
- `*.sqlite`
- `*.log`
- `data/garmin_health.csv`
- `~/.GarminDb/GarminConnectConfig.json`

Health data and logs are private runtime artifacts.

GarminDB CLI is unstable for automated sync usage.
Prefer controlled wrapper logic or internalized integration in v4+.
## GarminDB Usage Rule

GarminDB behavior and schema are unstable across versions.

Before modifying:
- automation/
- integrations/garmindb.py
- validation logic
- GarminDB SQL queries
- sync commands

the agent MUST:
1. Re-check the current GarminDB README and CLI help.
2. Verify actual local SQLite schema instead of assuming columns.
3. Prefer validation through real DB inspection over assumptions.
4. Treat GarminDB CLI as unreliable for production automation.
5. Keep all GarminDB-specific assumptions documented.

Known issue:
`garmindb_cli.py --download --latest`
may fail unless combined with:
`--all`
