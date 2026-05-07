def _to_float(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _average(values):
    if not values:
        return None
    return sum(values) / len(values)


def calculate_baseline(garmin_rows):
    recent_rows = sorted(garmin_rows, key=lambda row: row["date"])[-28:]

    sleep_hours = [_to_float(row.get("sleep_hours")) for row in recent_rows]
    body_battery = [_to_float(row.get("body_battery")) for row in recent_rows]
    resting_hr = [_to_float(row.get("resting_hr")) for row in recent_rows]

    baseline_status = "ready" if len(recent_rows) >= 7 else "insufficient_data"

    average_sleep_hours = _average(sleep_hours)
    average_body_battery = _average(body_battery)
    average_resting_hr = _average(resting_hr)

    return {
        "baseline_status": baseline_status,
        "average_sleep_hours": (
            round(average_sleep_hours, 1) if average_sleep_hours is not None else None
        ),
        "average_body_battery": (
            round(average_body_battery, 1) if average_body_battery is not None else None
        ),
        "average_resting_hr": (
            round(average_resting_hr, 1) if average_resting_hr is not None else None
        ),
        "days_analyzed": len(recent_rows),
    }
