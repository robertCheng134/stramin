# stramin

AI-powered Garmin recovery and training recommendation system.

This project is:

- Garmin-first
- optional Strava context
- optional GPT analysis

## Features

- recovery score
- trend analysis
- training decision engine
- personalized activity recommendation
- optional GPT analysis
- input validation
- Garmin CSV validation

## Morning Recovery Workflow

- enter morning Garmin metrics
- generate recovery score
- analyze trends
- produce training recommendation

## Run

```bash
pip install -r requirements.txt
cp .env.example .env
python3 src/morning_check.py
```

`OPENAI_API_KEY` is optional.

## Garmin CSV

The app reads Garmin health data from:

```text
data/garmin_health.csv
```

If that file does not exist, it falls back to:

```text
data/garmin_health_sample.csv
```

The real `data/garmin_health.csv` file is ignored by git because it may contain
personal health data.

Required columns:

```csv
date,sleep_hours,hrv_status,body_battery,resting_hr
```

Optional columns:

```csv
stress
```

Example:

```csv
date,sleep_hours,hrv_status,body_battery,resting_hr,stress
2026-05-06,5.8,low,45,56,51
```

Column notes:

- `date`: health record date, using `YYYY-MM-DD`
- `sleep_hours`: sleep duration in hours
- `hrv_status`: Garmin HRV status, such as `balanced`, `low`, `poor`, or `unbalanced`
- `body_battery`: Garmin Body Battery score
- `resting_hr`: resting heart rate
- `stress`: optional Garmin stress score

## Manual Entry

Add today's Garmin health data:

```bash
python3 src/add_garmin_entry.py
```

Add or update a specific date:

```bash
python3 src/add_garmin_entry.py --date 2026-05-01
```

Generate the daily report from existing CSV data:

```bash
python3 src/main.py
```

## Run Tests

```bash
python3 -m pytest
```
