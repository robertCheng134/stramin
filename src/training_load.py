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


DEFAULT_TRAINING_LOAD_PROFILE = {
    "weekly_training_minutes_baseline": 240,
    "high_load_multiplier": 1.3,
    "overreaching_3day_minutes_threshold": 180,
    "training_load_sensitivity": "moderate",
}


def _load_profile(user_profile):
    profile = DEFAULT_TRAINING_LOAD_PROFILE.copy()
    profile.update({key: value for key, value in (user_profile or {}).items() if value})
    profile["weekly_training_minutes_baseline"] = float(
        profile["weekly_training_minutes_baseline"]
    )
    profile["high_load_multiplier"] = float(profile["high_load_multiplier"])
    profile["overreaching_3day_minutes_threshold"] = float(
        profile["overreaching_3day_minutes_threshold"]
    )
    return profile


def _training_load_level(total_minutes, baseline, high_load_multiplier):
    low_threshold = baseline * 0.5
    high_threshold = baseline * high_load_multiplier

    if total_minutes < low_threshold:
        return "low"
    if total_minutes <= high_threshold:
        return "moderate"
    return "high"


def analyze_training_load(strava_activities, user_profile=None):
    profile = _load_profile(user_profile)
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
    baseline = profile["weekly_training_minutes_baseline"]
    high_threshold = baseline * profile["high_load_multiplier"]

    return {
        "last_7_days_total_minutes": round(last_7_days_total_minutes, 1),
        "last_3_days_total_minutes": round(last_3_days_total_minutes, 1),
        "activity_count_7_days": len(activities_7_days),
        "training_load_level": _training_load_level(
            last_7_days_total_minutes,
            baseline,
            profile["high_load_multiplier"],
        ),
        "overreaching_risk": (
            last_3_days_total_minutes
            > profile["overreaching_3day_minutes_threshold"]
        ),
        "weekly_training_minutes_baseline": round(baseline, 1),
        "high_load_threshold": round(high_threshold, 1),
        "overreaching_3day_minutes_threshold": round(
            profile["overreaching_3day_minutes_threshold"],
            1,
        ),
        "training_load_sensitivity": profile["training_load_sensitivity"],
    }
