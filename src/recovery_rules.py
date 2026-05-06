LOW_HRV_STATUSES = {"low", "poor", "unbalanced"}


def _to_float(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_recovery(garmin_health):
    score = 100

    sleep_hours = _to_float(garmin_health.get("sleep_hours"))
    hrv_status = str(garmin_health.get("hrv_status") or "").strip().lower()
    body_battery = _to_float(garmin_health.get("body_battery"))
    stress_value = garmin_health.get("stress")
    stress = _to_float(stress_value) if stress_value not in (None, "") else None

    if sleep_hours < 6:
        score -= 25

    if hrv_status in LOW_HRV_STATUSES:
        score -= 20

    if body_battery < 50:
        score -= 15

    if stress is not None and stress > 50:
        score -= 10

    recovery_score = max(0, min(100, score))

    if recovery_score >= 80:
        recovery_level = "good"
    elif recovery_score >= 60:
        recovery_level = "moderate"
    else:
        recovery_level = "poor"

    return {
        "recovery_score": recovery_score,
        "recovery_level": recovery_level,
    }
