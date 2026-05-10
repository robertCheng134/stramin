from datetime import date, timedelta


def _value_or_unknown(value):
    if value in (None, ""):
        return "unavailable"
    return value


def _decision_value(decision, key):
    if not isinstance(decision, dict):
        return "unavailable"
    return _value_or_unknown(decision.get(key))


def _finalized_data_note(latest_recovery_date):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if latest_recovery_date == yesterday:
        return (
            f"Latest finalized Garmin recovery data is from {latest_recovery_date}."
        )
    return ""


def format_daily_telegram_report(daily_state, recommendation_preview=None):
    recommendation_preview = recommendation_preview or {}
    decision = recommendation_preview.get("decision") or daily_state.get("decision", {})
    hrv = daily_state.get("hrv", {})
    latest_recovery_date = daily_state.get("latest_recovery_date") or daily_state.get(
        "date",
        "",
    )
    rationale = recommendation_preview.get("rationale") or daily_state.get(
        "rationale",
        "",
    )

    lines = [
        "Stramin Daily Report",
        f"latest_recovery_date: {_value_or_unknown(latest_recovery_date)}",
    ]
    finalized_note = _finalized_data_note(latest_recovery_date)
    if finalized_note:
        lines.append(finalized_note)

    lines.extend(
        [
            "",
            "Garmin recovery",
            f"sleep_hours: {_value_or_unknown(daily_state.get('sleep_hours'))}",
            f"hrv: {_value_or_unknown(hrv.get('hrv_value'))} {_value_or_unknown(hrv.get('hrv_unit', 'ms'))}",
            f"hrv_balance: {_value_or_unknown(hrv.get('hrv_balance'))}",
            f"stress: {_value_or_unknown(daily_state.get('stress'))}",
        ]
    )

    if daily_state.get("resting_hr") not in (None, ""):
        lines.append(f"resting_hr: {daily_state['resting_hr']}")

    lines.extend(
        [
            "",
            "Recommendation",
            f"decision: {_decision_value(decision, 'decision')}",
            f"intensity: {_decision_value(decision, 'intensity')}",
            f"suggested_activity: {_decision_value(decision, 'suggested_activity')}",
            f"recommendation: {_value_or_unknown(recommendation_preview.get('recommendation') or daily_state.get('recommendation'))}",
            f"rationale: {_value_or_unknown(rationale)}",
        ]
    )

    return "\n".join(lines)


def format_warning_telegram_report(reason, latest_recovery_date=""):
    lines = [
        "Stramin Daily Report Delayed",
        "No training recommendation was sent.",
    ]
    if latest_recovery_date:
        lines.append(f"latest_recovery_date: {latest_recovery_date}")
    lines.append(f"reason: {_value_or_unknown(reason)}")
    return "\n".join(lines)
