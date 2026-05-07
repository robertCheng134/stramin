from datetime import datetime, timedelta, timezone


def _to_minutes(activity):
    try:
        return int(activity.get("moving_time") or 0) / 60
    except (TypeError, ValueError):
        return 0


def _parse_start_date(activity):
    start_date = activity.get("start_date")
    if not start_date:
        return None

    try:
        return datetime.fromisoformat(start_date.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _is_within_window(activity, window_start, now):
    start_date = _parse_start_date(activity)
    if not start_date:
        return True

    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)

    return window_start <= start_date <= now


def _training_load_level(total_minutes):
    if total_minutes < 90:
        return "low"
    if total_minutes <= 240:
        return "moderate"
    return "high"


def analyze_training_load(strava_activities):
    activities = strava_activities or []
    now = datetime.now(timezone.utc)
    last_7_days = now - timedelta(days=7)
    last_3_days = now - timedelta(days=3)

    activities_7_days = [
        activity
        for activity in activities
        if _is_within_window(activity, last_7_days, now)
    ]
    activities_3_days = [
        activity
        for activity in activities
        if _is_within_window(activity, last_3_days, now)
    ]

    last_7_days_total_minutes = sum(_to_minutes(activity) for activity in activities_7_days)
    last_3_days_total_minutes = sum(_to_minutes(activity) for activity in activities_3_days)

    return {
        "last_7_days_total_minutes": round(last_7_days_total_minutes, 1),
        "last_3_days_total_minutes": round(last_3_days_total_minutes, 1),
        "activity_count_7_days": len(activities_7_days),
        "training_load_level": _training_load_level(last_7_days_total_minutes),
        "overreaching_risk": last_3_days_total_minutes > 180,
    }
