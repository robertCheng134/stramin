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
sqlite3 ~/HealthData/DBs/garmin.db "select count(*) from hrv;"
sqlite3 ~/HealthData/DBs/garmin.db "select count(*) from sleep;"
sqlite3 ~/HealthData/DBs/garmin.db "select count(*) from stress;"
sqlite3 ~/HealthData/DBs/garmin.db "select count(*) from daily_summary;"
```

Inspect Stramin interpretation:

```bash
python3 scripts/test_garmindb_today.py --db-dir ~/HealthData/DBs --debug
python3 scripts/preview_garmindb_recommendation.py --db-dir ~/HealthData/DBs
```

## Metric Semantics

- sleep: `garmin.db.sleep.total_sleep`
- stress: latest valid `garmin.db.stress.stress` where `stress >= 0`
- official resting HR: `garmin.db.resting_hr.resting_heart_rate`
- HRV nightly average: `garmin.db.hrv.last_night_avg`
- HRV fallback: `garmin_monitoring.db.monitoring_hrv_status.last_night`
- HRV 5-minute high: `last_night_5min_high` or monitoring fallback
  `last_night_average`

Negative stress values are invalid/unclassified and are skipped.

## Privacy

Do not commit GarminDB files, logs, credentials, or derived health exports.

