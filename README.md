# stramin

AI-powered Garmin recovery and training recommendation system.

## Project Vision

stramin is a Garmin-first training assistant that turns daily health signals,
recent training load, and personal preferences into practical recovery and
training recommendations.

The goal is to make training decisions less reactive and more adaptive: respect
the plan, listen to the body, and adjust before fatigue becomes a problem.

## v2.0.0 Dynamic Adaptive Training Coach

v2.0.0 introduces a Dynamic Adaptive Training Coach built around three ideas:

- Garmin health data is the primary source of truth.
- Strava activity history is optional context for training load.
- GPT analysis is optional narrative coaching, not a hard dependency.

The system can now compare planned workouts against current recovery, fatigue
trend, and training load, then produce adjusted weekly recommendations.

## Architecture Overview

The app is intentionally modular:

- Garmin CSV data is loaded, validated, and normalized.
- Recovery rules calculate a daily recovery score and level.
- Trend analysis summarizes recent Garmin health patterns.
- Training load analysis evaluates recent Strava activity volume when available.
- The decision engine recommends today’s training direction.
- The weekly planner adapts planned workouts into a safer 7-day plan.
- Report formatters generate readable daily and weekly output.

The main flows are:

```bash
python3 src/morning_check.py
python3 src/main.py
```

`morning_check.py` is the guided morning workflow. `main.py` generates reports
from existing data.

## Core Modules

- `src/garmin_health.py`: reads and validates Garmin CSV data.
- `src/add_garmin_entry.py`: interactively adds or updates Garmin health rows.
- `src/morning_check.py`: captures today’s Garmin metrics and generates a report.
- `src/recovery_rules.py`: calculates recovery score and recovery level.
- `src/baseline.py`: calculates adaptive personal Garmin baselines.
- `src/trend_analysis.py`: analyzes recent Garmin health trends.
- `src/strava.py`: fetches optional recent Strava activities.
- `src/training_load.py`: calculates personalized training load from Strava data.
- `src/decision_engine.py`: recommends today’s training decision.
- `src/weekly_planner.py`: adapts planned workouts into a weekly training plan.
- `src/daily_report.py`: formats the daily recovery report.
- `src/weekly_report.py`: formats the weekly training plan.
- `src/gpt_analysis.py`: adds optional GPT coaching analysis.
- `src/user_profile.py`: loads user preferences and planning configuration.

## Data Sources

### Garmin CSV

Garmin health data is the foundation of the system.

The app reads:

```text
data/garmin_health.csv
```

If that file does not exist, it falls back to:

```text
data/garmin_health_sample.csv
```

`data/garmin_health.csv` is ignored by git because it may contain personal
health data.

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

Validation rules:

- `date`: `YYYY-MM-DD`
- `sleep_hours`: `0` to `24`
- `hrv_status`: `balanced`, `low`, `poor`, or `unbalanced`
- `body_battery`: `0` to `100`
- `resting_hr`: `20` to `120`
- `stress`: optional

Invalid rows are skipped and never enter analysis or reports.

### Optional Strava Context

Strava is used only when `STRAVA_ACCESS_TOKEN` is available.

Recent activities are used to calculate:

- 7-day training minutes
- 3-day training minutes
- activity count
- personalized training load level
- overreaching risk

If Strava is unavailable, reports still run with `training_load = None`.

### Optional GPT Analysis

GPT coaching is used only when `OPENAI_API_KEY` is available.

If the key is missing, quota is exhausted, or the API raises an error, the app
prints:

```text
GPT skipped: <error>
```

The system then continues with rule-based reporting, training decisions, and
weekly planning.

## User Profile

Personal settings live in:

```text
config/user_profile.json
```

The profile controls preferred activities, disliked activities, training goals,
weekly structure, dynamic workout adaptation, and personalized training load
thresholds.

Example:

```json
{
  "preferred_activities": ["weight_training", "walking", "cycling"],
  "disliked_activities": ["hiit"],
  "training_goal": "general_fitness",
  "weekly_training_minutes_baseline": 240,
  "high_load_multiplier": 1.3,
  "overreaching_3day_minutes_threshold": 180,
  "training_load_sensitivity": "moderate",
  "weekly_structure": {
    "Monday": "weight_training",
    "Tuesday": "walking",
    "Wednesday": "rest",
    "Thursday": "weight_training",
    "Friday": "cycling",
    "Saturday": "weight_training",
    "Sunday": "rest"
  },
  "planned_workouts": {
    "Monday": {
      "activity": "weight_training",
      "focus": "legs",
      "intensity": "high"
    },
    "Tuesday": {
      "activity": "cycling",
      "intensity": "moderate"
    }
  },
  "priority_muscle_groups": ["chest", "back", "legs"],
  "preferred_training_time": "evening",
  "rest_days": ["Sunday"],
  "session_duration_minutes": 60
}
```

## Weekly Planner and Dynamic Adaptation

The weekly planner starts from `planned_workouts` and `weekly_structure`, then
adapts each day based on:

- recovery level
- fatigue trend
- training load level
- overreaching risk
- rest days
- disliked activities

Each weekly plan item includes:

- `planned_activity`
- `adjusted_activity`
- `original_intensity`
- `adjusted_intensity`
- `adaptation_reason`

Examples of adaptation:

- Poor recovery can turn high intensity training into a recovery walk.
- Overreaching risk lowers moderate or high intensity by one level.
- Worsening fatigue adds recovery sessions.
- Rest days remain rest days.

## Running the App

Install dependencies:

```bash
pip install -r requirements.txt
```

Create local environment config:

```bash
cp .env.example .env
```

Run the guided morning workflow:

```bash
python3 src/morning_check.py
```

Generate reports from existing CSV data:

```bash
python3 src/main.py
```

Manually add or update a Garmin entry:

```bash
python3 src/add_garmin_entry.py
python3 src/add_garmin_entry.py --date 2026-05-01
```

## Testing

Run the full test suite:

```bash
python3 -m pytest
```

Current coverage includes:

- recovery scoring
- baseline calculation
- Garmin CSV validation behavior
- decision engine outcomes
- training load personalization
- weekly planner behavior
- dynamic workout adaptation

## Roadmap

- Garmin API import when a reliable integration path is chosen.
- richer trend scoring across sleep, HRV, resting HR, and body battery.
- muscle-group rotation for planned strength sessions.
- workout history feedback loops for progressive overload.
- report export to Markdown, email, or calendar.
- safer Strava token refresh handling.
- expanded tests for end-to-end morning workflows.
