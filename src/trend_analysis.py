from garmin_health import load_garmin_health_rows


HRV_STATUS_SCORES = {
    "poor": 0,
    "low": 1,
    "unbalanced": 1,
    "balanced": 2,
    "optimal": 3,
}


def _to_float(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _average(values):
    if not values:
        return 0
    return sum(values) / len(values)


def _trend_from_delta(delta, positive_label, negative_label, stable_label="stable"):
    if delta > 3:
        return positive_label
    if delta < -3:
        return negative_label
    return stable_label


def _hrv_score(status):
    return HRV_STATUS_SCORES.get(str(status or "").strip().lower(), 1)


def analyze_recent_trends(csv_path=None, days=7):
    rows = sorted(load_garmin_health_rows(csv_path), key=lambda row: row["date"])[-days:]

    sleep_values = [_to_float(row.get("sleep_hours")) for row in rows]
    stress_values = [
        _to_float(row.get("stress"))
        for row in rows
        if row.get("stress") not in (None, "")
    ]
    body_battery_values = [_to_float(row.get("body_battery")) for row in rows]
    hrv_statuses = [row.get("hrv_status") for row in rows]

    average_sleep = _average(sleep_values)
    average_stress = _average(stress_values) if stress_values else None

    body_battery_delta = body_battery_values[-1] - body_battery_values[0]
    stress_delta = stress_values[-1] - stress_values[0] if len(stress_values) >= 2 else 0
    hrv_delta = _hrv_score(hrv_statuses[-1]) - _hrv_score(hrv_statuses[0])

    body_battery_trend = _trend_from_delta(
        body_battery_delta,
        positive_label="up",
        negative_label="down",
    )

    fatigue_signal = stress_delta - body_battery_delta
    fatigue_trend = _trend_from_delta(
        fatigue_signal,
        positive_label="worsening",
        negative_label="improving",
    )

    recovery_signal = body_battery_delta + (hrv_delta * 5)
    recovery_trend = _trend_from_delta(
        recovery_signal,
        positive_label="recovering",
        negative_label="declining",
    )

    hrv_status_change = (
        "stable"
        if hrv_statuses[0] == hrv_statuses[-1]
        else f"{hrv_statuses[0]} -> {hrv_statuses[-1]}"
    )

    stress_summary = (
        f"平均壓力 {average_stress:.1f}。"
        if average_stress is not None
        else "未提供 stress 資料。"
    )
    trend_summary = (
        f"最近 {len(rows)} 筆資料平均睡眠 {average_sleep:.1f} 小時，"
        f"{stress_summary}"
        f"Body Battery 趨勢為 {body_battery_trend} "
        f"({body_battery_values[0]:.0f} -> {body_battery_values[-1]:.0f})，"
        f"HRV 狀態變化為 {hrv_status_change}。"
    )

    return {
        "trend_summary": trend_summary,
        "fatigue_trend": fatigue_trend,
        "recovery_trend": recovery_trend,
        "average_sleep": round(average_sleep, 1),
        "average_stress": round(average_stress, 1) if average_stress is not None else None,
        "body_battery_trend": body_battery_trend,
        "hrv_status_change": hrv_status_change,
        "days_analyzed": len(rows),
    }
