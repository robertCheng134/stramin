# GarminDB Operations

Operational notes for running GarminDB with Stramin v4.

## Paths

- GarminDB config: `~/.GarminDb/GarminConnectConfig.json`
- health data root: `~/HealthData`
- main database: `~/HealthData/DBs/garmin.db`
- monitoring database: `~/HealthData/DBs/garmin_monitoring.db`
- Stramin virtualenv: `~/stramin/.venv`

`GARMINDB_PATH` points to a local SQLite file. It is not a Garmin username,
password, token, or credential.

## Preferred Sync Command

Run GarminDB sync jobs inside `tmux`:

```bash
tmux new -s stramin-sync
cd ~/stramin
source .venv/bin/activate
garmindb_cli.py --all --download --import --analyze --latest
```

Detach with `Ctrl-b d`.

Reattach:

```bash
tmux attach -t stramin-sync
```

## Known GarminDB Issue

This command may fail:

```bash
garmindb_cli.py --download
```

Known error:

```text
TypeError: argument of type 'NoneType' is not iterable
```

Prefer the full pipeline:

```bash
garmindb_cli.py --all --download --import --analyze --latest
```

## Validation Commands

Run these before trusting a new sync:

```bash
sqlite3 ~/HealthData/DBs/garmin.db "select max(day), count(*) from daily_summary;"
sqlite3 ~/HealthData/DBs/garmin.db "select count(*) from hrv;"
sqlite3 ~/HealthData/DBs/garmin.db "select count(*) from sleep;"
sqlite3 ~/HealthData/DBs/garmin.db "select count(*) from stress;"
sqlite3 ~/HealthData/DBs/garmin.db "select count(*) from daily_summary;"
```

Verified latest-data checks:

```bash
sqlite3 ~/HealthData/DBs/garmin.db "select day, last_night_avg, status from hrv order by day desc limit 1;"
sqlite3 ~/HealthData/DBs/garmin.db "select day, total_sleep from sleep order by day desc limit 1;"
sqlite3 ~/HealthData/DBs/garmin.db "select day, rhr, stress_avg, bb_charged from daily_summary order by day desc limit 1;"
```

Inspect Stramin interpretation:

```bash
python3 scripts/test_garmindb_today.py --db-dir ~/HealthData/DBs --debug
python3 scripts/preview_garmindb_recommendation.py --db-dir ~/HealthData/DBs
```

## Metric Semantics

- production freshness: `garmin.db.daily_summary.day`
- resting HR: prefer `garmin.db.daily_summary.rhr`
- stress: prefer `garmin.db.daily_summary.stress_avg`
- body battery: prefer `garmin.db.daily_summary.bb_charged`, then `bb_max`, then `bb_min`
- waking respiration: `garmin.db.daily_summary.rr_waking_avg`
- sleep: use raw `garmin.db.sleep.total_sleep` only as same-day supplemental data
- HRV nightly average: use raw `garmin.db.hrv.last_night_avg` only as same-day supplemental data
- HRV fallback: `garmin_monitoring.db.monitoring_hrv_status.last_night`
- HRV 5-minute high: `last_night_5min_high` or monitoring fallback
  `last_night_average`

Negative stress values are invalid/unclassified and are skipped.

## Production Freshness Findings

Production verification confirmed that GarminDB raw tables such as `hrv` and
`sleep` are usable. The important rule is to never order GarminDB health tables
by `rowid`. After GarminDB bulk import/analyze, `rowid` does not represent
chronological order and can make fresh data look stale.

Always order by the business date column:

- `hrv.day`
- `sleep.day`
- `daily_summary.day`

For v4 production stability, Stramin treats `daily_summary` as the primary
recovery source and validates freshness from `daily_summary.day`. Summary rows
are preferred because they represent Garmin's finalized daily view.

Operational rule:

- trust `daily_summary.day` for readiness/freshness
- prefer summary columns for recovery metrics where available
- use raw `sleep` and `hrv` when needed, ordered by `day desc`
- never use `rowid` as a proxy for latest health data
- do not send a Telegram recommendation when `daily_summary.day` is stale

Garmin finalized recovery data can naturally lag by one day. If the latest
finalized recovery date is yesterday, that is normal and accepted by v4
validation. Data older than yesterday is treated as too stale for automatic
recommendations.

## Privacy

Do not commit GarminDB files, logs, credentials, or derived health exports.
