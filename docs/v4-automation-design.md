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
GarminDB sync
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

If validation fails, send no proactive recommendation. A manual `/today` command
may still show a graceful fallback or ask the user to use `/entry`.

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
garmindb_cli.py --all --download --import --analyze --latest
python3 scripts/preview_garmindb_recommendation.py --db-dir ~/HealthData/DBs
```

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

