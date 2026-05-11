# AGENTS.md

Guidance for Codex and contributors working on Stramin.

## 1. Mission

Stramin provides reliable Garmin-first recovery and training recommendations
from local health data. The project values operational transparency, privacy,
and stable rule-based behavior over clever automation.

## 2. Current Status

- Branch focus: `feature/garmindb-today-flow`.
- Release track: v4 infrastructure and production stability.
- v4 priority: GarminDB ingestion, validation, daily state, Telegram delivery, logging, setup, deployment.
- v5 direction: AI coaching, richer personalization, and orchestration.
- Do not add AI coaching features in v4.

## 3. Architecture Boundaries

```text
GarminDB / CSV / manual input
        |
        v
HealthData
        |
        +--> recovery_rules.py
        +--> decision_engine.py
        +--> weekly_planner.py
        |
        +--> daily_state.json
        +--> CLI previews
        +--> Telegram reports
```

- Garmin is the primary recovery source.
- GarminDB is the production ingestion backend.
- Garmin CSV/manual entry remain fallback and development workflows.
- Strava is activity/training-load context only.
- GPT/AI is optional narrative context only, not decision authority.
- `recovery_rules.py`, `decision_engine.py`, and `weekly_planner.py` should stay stable unless explicitly requested.

## 4. Change Categories

Safe changes:

- Docs and comments.
- Local helper extraction.
- Clearer metadata.
- Safer fallback handling.
- Clearer logs, messages, or operator guidance.

Requires tests:

- Ingestion changes.
- Validation changes.
- Formatting changes.
- SQL queries.
- Fallback behavior.
- `daily_state.json` contract changes.
- Telegram behavior.
- Setup or automation pipeline behavior.

Requires explicit approval:

- Recovery semantics.
- Decision engine behavior.
- HRV meaning or baseline interpretation.
- Dependency changes.
- Architecture redesign.
- Duplicate-send, retry, or validation rule changes.
- AI coaching or autonomous planning.
- Destructive git/file operations.
- Commits or pushes.

## 5. Forbidden Changes

Do not:

- Remove or weaken tests.
- Commit `.env`, credentials, logs, databases, or health data.
- Order GarminDB health tables by `rowid`.
- Run full GarminDB sync without `--latest`.
- Auto-run GarminDB sync/download/import from Telegram.
- Hide sync/validation failures behind silent fallback behavior.
- Introduce fake AI coaching logic.
- Replace deterministic rules with GPT output.
- Rewrite unrelated modules during focused tasks.

## 6. Testing Expectations

Default test command:

```bash
python3 -m pytest
```

For GarminDB ingestion or recommendation preview work, also run when local DBs are available:

```bash
python3 scripts/test_garmindb_today.py --db-dir ~/HealthData/DBs --debug
python3 scripts/preview_garmindb_recommendation.py --db-dir ~/HealthData/DBs
```

Testing rules:

- Use temporary SQLite databases in tests.
- Do not require real Garmin credentials.
- Do not make real Telegram network calls.
- Do not depend on private local health data.
- Report tests run and results in the handoff.

## 7. GarminDB Rules

Paths:

- config: `~/.GarminDb/GarminConnectConfig.json`
- health root: `~/HealthData`
- main DB: `~/HealthData/DBs/garmin.db`
- monitoring DB: `~/HealthData/DBs/garmin_monitoring.db`
- Stramin virtualenv: `~/stramin/.venv`

Install and verify:

```bash
pip install -r requirements.txt
which garmindb_cli.py
```

Preferred Stramin-managed sync:

```bash
python3 automation/run_garmindb_sync.py
```

Production daily pipeline:

```bash
python3 automation/run_daily_pipeline.py --sync-garmin --db-dir ~/HealthData/DBs
```

Safety rules:

- Raw `garmindb_cli.py` is troubleshooting detail, not the normal interface.
- Never run full GarminDB sync without `--latest`.
- GarminDB schemas can vary; inspect actual SQLite schema before changing SQL.
- Validate assumptions with real table/column checks where practical.
- Keep GarminDB-specific assumptions documented.

Ordering rules:

- Never order GarminDB health tables by `rowid`.
- `rowid` is not chronological after bulk import/analyze.
- Always order by business date columns:
  - `hrv.day`
  - `sleep.day`
  - `daily_summary.day`

Freshness rules:

- v4 validates readiness from `daily_summary.day`.
- Latest finalized Garmin recovery data may be yesterday.
- Today and yesterday are accepted.
- Older data is too stale for automatic Telegram recommendations.

Useful inspection queries:

```bash
sqlite3 ~/HealthData/DBs/garmin.db "select day, last_night_avg, status from hrv order by day desc limit 1;"
sqlite3 ~/HealthData/DBs/garmin.db "select day, total_sleep from sleep order by day desc limit 1;"
sqlite3 ~/HealthData/DBs/garmin.db "select day, rhr, stress_avg, bb_charged from daily_summary order by day desc limit 1;"
```

Known GarminDB instability:

```text
garmindb_cli.py --download
TypeError: argument of type 'NoneType' is not iterable
```

Known CLI rule:

- `garmindb_cli.py --download --latest` may fail unless combined with `--all`.

Use the Stramin wrapper and keep failures visible.

## 8. Deployment / Runtime Rules

- Use `tmux` for long-running sync or pipeline runs until systemd is intentionally added.
- Validate DB data before publishing Telegram recommendations.
- Write runtime logs to `logs/`.
- Write `daily_state.json` atomically.
- Do not send Telegram recommendations on stale or invalid data.
- Prevent duplicate Telegram reports for the same local date.
- Dry-run must never send Telegram or mark `telegram_sent=true`.

tmux example:

```bash
tmux new -s stramin-sync
source ~/stramin/.venv/bin/activate
python3 automation/run_daily_pipeline.py --sync-garmin --db-dir ~/HealthData/DBs
```

Detach with `Ctrl-b d`; reattach with:

```bash
tmux attach -t stramin-sync
```

## 9. Data Privacy Rules

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

Also avoid printing secret values in logs, tests, docs, or CLI output.

## 10. Definition of Done

Before handoff:

- Changed files are reported.
- Relevant tests are run.
- Test results are reported.
- No private data is added.
- Behavior changes are explicitly stated.
- Risky assumptions are documented.
- Product behavior is preserved unless explicitly changed.
- No commit is created unless explicitly requested.
