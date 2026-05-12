# First-run Onboarding

Stramin owns the normal setup flow. Users should not manually create virtual
environments, install requirements step-by-step, edit template files, or run raw
GarminDB commands.

## Normal Flow

```bash
git clone https://github.com/robertCheng134/stramin.git
cd stramin
python3 automation/bootstrap.py --interactive
.venv/bin/python automation/run_garmindb_sync.py --timeout 0
.venv/bin/python automation/run_morning_scheduler.py --db-dir ~/HealthData/DBs
```

## What Bootstrap Does

`automation/bootstrap.py --interactive`:

- creates `.venv` if it is missing
- installs `requirements.txt` inside `.venv`
- runs Stramin `.env` setup
- preserves existing `.env` values
- restores secrets from `~/.stramin.env.backup` when available
- auto-fills:
  - `GARMINDB_DIR=~/HealthData/DBs`
  - `GARMINDB_PATH=~/HealthData/DBs/garmin.db`
- verifies GarminDB tooling through the virtualenv
- prints Stramin-level next steps

## Interactive Secrets

Stramin prompts only for user-owned secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `GARMIN_EMAIL`
- `GARMIN_PASSWORD`
- optional `OPENAI_API_KEY`
- optional `STRAVA_ACCESS_TOKEN`

`GARMIN_PASSWORD` is entered with hidden input. Secret values are not printed.

After successful setup, Stramin writes `~/.stramin.env.backup` so future clones
can restore local secrets automatically.

## What Users Should Not Do

Normal users should not:

- manually edit `requirements.txt`
- manually edit `.env.example`
- manually set `GARMINDB_PATH`
- manually set `GARMINDB_DIR`
- normally run raw GarminDB CLI commands
- create `.venv` by hand
- run manual `pip install` steps
- use a raw infinite five-minute loop

## Garmin Bootstrap

First Garmin bootstrap can take hours because GarminDB may download monitoring
data, import records, analyze databases, and perform SQLite processing.

Use Stramin's wrapper:

```bash
.venv/bin/python automation/run_garmindb_sync.py --timeout 0
```

GarminDB still stores its own session/config under:

```text
~/.GarminDb
```

## Daily Operation

Daily operation uses the morning scheduler:

```bash
.venv/bin/python automation/run_morning_scheduler.py --db-dir ~/HealthData/DBs
```

The scheduler runs only during the morning delivery window, retries safely, and
does not keep syncing GarminDB all day.
