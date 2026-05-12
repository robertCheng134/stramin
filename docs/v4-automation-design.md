# v4 Automation Design

Design target for Stramin v4 operational automation.

## Goals

- run GarminDB sync safely
- validate data before recommendations
- publish Telegram output only after validation
- protect users from stale or invalid health data
- keep failures visible and recoverable

No AI coaching belongs in this design. v5 will handle AI.

## Nightly Pipeline

```text
tmux/systemd/cron trigger
        |
        v
Stramin-managed GarminDB sync
        |
        v
SQLite validation
        |
        v
latest HealthData extraction
        |
        v
atomic daily_state.json write
        |
        v
Telegram push
```

## Validation Before Recommendation

Required checks:

- `~/HealthData/DBs/garmin.db` exists
- `~/HealthData/DBs/garmin_monitoring.db` exists when HRV fallback is needed
- `hrv`, `sleep`, `stress`, `resting_hr`, `daily_summary` tables are queryable
- latest finalized recovery date is acceptable
- stress selection skips invalid negative rows
- recommendation preview can be generated

If validation fails, do not publish a Telegram recommendation.

## Atomic daily_state.json

Future automation should write state atomically:

1. build state in memory
2. write to `daily_state.json.tmp`
3. fsync if practical
4. rename to `daily_state.json`

Never publish from a partially written state file.

Suggested contents:

```json
{
  "generated_at": "2026-05-10T06:00:00+08:00",
  "latest_recovery_date": "2026-05-09",
  "validation_status": "ready",
  "recommendation": "light_training",
  "metrics": {
    "sleep_hours": "6.5",
    "hrv_value": "32",
    "resting_hr": "62"
  }
}
```

## Telegram Publish Gate

Send Telegram output only when:

- sync command completed
- validation passed
- daily state was atomically written
- latest data is not stale beyond the configured tolerance
- no Telegram report has already been sent for the same local date

If validation fails, send no proactive recommendation. A manual `/today` command
may still show a graceful fallback or ask the user to use `/entry`.

## Scheduled Readiness Retry

The daily Telegram report is intended to run around `09:00`, but Garmin
sleep, HRV, and resting heart rate can lag behind the user's morning. The
automation must treat readiness as a gate, not as a best-effort suggestion.

Default schedule config:

- `STRAMIN_DAILY_REPORT_TIME=09:00`
- `STRAMIN_RETRY_INTERVAL_MINUTES=5`
- `STRAMIN_RETRY_CUTOFF_TIME=11:00`

Behavior:

1. At `09:00`, run the daily pipeline.
2. If validation passes, build `daily_state.json`, build the recommendation
   preview, and publish immediately when a safe sender exists.
3. If validation fails before the cutoff because data is not ready, log the
   failure, send no Telegram message, and exit with a retryable status. The
   scheduler can call the same command again after the retry interval.
4. Retry every 5 minutes by default.
5. Stop retrying after the cutoff time, default `11:00`.
6. After cutoff, send only a warning/status message if a warning sender exists.
   Do not send a training recommendation based on unvalidated data.
7. Prevent duplicate Telegram training reports for the same local date.

v4 does not introduce a background daemon. Retry is a stateful, synchronous
pipeline behavior that a future cron/systemd timer can call repeatedly.

## Notification State

The retry gate uses a small local state file:

`data/notification_state.json`

Suggested shape:

```json
{
  "date": "2026-05-10",
  "telegram_sent": false,
  "sent_at": "",
  "last_attempt_at": "2026-05-10T09:05:00+08:00",
  "retry_count": 1,
  "final_failure_sent": false
}
```

Rules:

- reset state automatically when the local date changes
- if `telegram_sent=true` for today, the pipeline must no-op
- update `last_attempt_at` and `retry_count` on validation failures
- set `telegram_sent=true` only after a real Telegram send succeeds
- set `final_failure_sent=true` only after a final warning/status send succeeds
- dry-run mode must never mark `telegram_sent=true`

## Stale-Data Protection

The system should compare `latest_recovery_date` with local current date.

If stale:

- show `Latest finalized Garmin recovery data is from YYYY-MM-DD.`
- avoid pretending the recommendation is based on today's finalized Garmin data
- log the stale state

## Sync Failure Handling

On GarminDB failure:

- keep previous valid `daily_state.json`
- write failure details to logs
- do not overwrite valid state with partial data
- do not auto-run hidden recovery commands
- require operator inspection for repeated failures

Operators should use Stramin's wrapper instead of raw GarminDB CLI:

```bash
python3 automation/run_garmindb_sync.py
```

The production daily pipeline should use managed sync:

```bash
python3 automation/run_daily_pipeline.py --sync-garmin --db-dir ~/HealthData/DBs
```

Raw `garmindb_cli.py` is an implementation detail for troubleshooting only.
Never run a full GarminDB sync without `--latest`.

## Logging Strategy

Recommended log locations:

- `logs/garmindb-sync.log`
- `logs/validation.log`
- `logs/telegram-bot.log`

Logs should include:

- command started/finished
- DB path
- validation status
- selected metric source
- invalid rows skipped
- stale-data warnings
- exception summary

Logs must not include Garmin credentials.

## tmux Workflow

Use `tmux` until cron/systemd automation is intentionally introduced:

```bash
tmux new -s stramin-sync
cd ~/stramin
source .venv/bin/activate
python3 automation/run_morning_scheduler.py --db-dir ~/HealthData/DBs
```

The scheduler replaces raw infinite loops such as:

```bash
while true; do
  python3 automation/run_daily_pipeline.py --sync-garmin --db-dir ~/HealthData/DBs
  sleep 300
done
```

It waits until the morning delivery window, retries only between `09:00` and
`11:00`, stops after the report is sent or already marked sent, and does not
sync GarminDB continuously all day. After cutoff, any final pipeline handling
runs without `--sync-garmin`.

Detach with `Ctrl-b d`.

## Future cron/systemd

Future automation can move from `tmux` to `cron` or `systemd` when:

- sync command is stable
- logs are rotated
- validation gate exists
- stale-data threshold is configured
- Telegram publish is idempotent
- failure notifications are clear

Until then, prefer manual `tmux` operation for production safety.

A future systemd service/timer should eventually call the scheduler or an
equivalent controlled daily trigger:

```bash
python3 automation/run_morning_scheduler.py --db-dir ~/HealthData/DBs
```
