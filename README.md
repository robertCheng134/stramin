# stramin

Garmin-first recovery analysis with optional Strava activity context.

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
date,sleep_hours,hrv_status,body_battery,resting_hr,stress
```

Example:

```csv
date,sleep_hours,hrv_status,body_battery,resting_hr,stress
2026-05-06,5.8,low,45,56,51
```

Column notes:

- `date`: activity or health record date, using `YYYY-MM-DD`
- `sleep_hours`: sleep duration in hours
- `hrv_status`: Garmin HRV status, such as `balanced`, `low`, `poor`, or `unbalanced`
- `body_battery`: Garmin Body Battery score
- `resting_hr`: resting heart rate
- `stress`: Garmin stress score

## Run

```bash
pip install -r requirements.txt
cp .env.example .env
python3 src/main.py
```

`OPENAI_API_KEY` is optional. If it is missing, the app prints the rule-based
recovery score and skips GPT analysis.
