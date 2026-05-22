from datetime import date, timedelta

from reports.localization import localized_text as t


def _value_or_unknown(value):
    if value in (None, ""):
        return t("common.unavailable")
    return value


def _format_float(value, digits=1, suffix=""):
    if value in (None, ""):
        return "unavailable"
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return f"{value}{suffix}"


def _format_int(value, suffix=""):
    if value in (None, ""):
        return "unavailable"
    try:
        return f"{round(float(value))}{suffix}"
    except (TypeError, ValueError):
        return f"{value}{suffix}"


def _humanize_token(value):
    text = str(_value_or_unknown(value)).strip()
    replacements = {
        "light_training": "Light training",
        "recovery_day": "Recovery day",
        "rest": "Rest",
        "train": "Train",
        "weight_training": "Weight training",
        "low to moderate": "Light to moderate",
        "normal": "Normal",
        "moderate": "Moderate",
        "high": "High",
        "low": "Low",
    }
    lowered = text.lower()
    if lowered in replacements:
        return replacements[lowered]
    return text.replace("_", " ").capitalize()


def _humanize_plan(value):
    text = str(_value_or_unknown(value)).strip()
    if " / " not in text:
        return _humanize_token(text)
    return " / ".join(_humanize_token(part) for part in text.split(" / "))


def _humanize_hrv_balance(value):
    mapping = {
        "below_baseline": "Below baseline",
        "above_baseline": "Above baseline",
        "within_baseline": "Within baseline",
        "stable": "Within baseline",
        "unknown": "Unknown",
    }
    return mapping.get(str(value or "").strip().lower(), _humanize_token(value))


def _shorten_rationale(value):
    text = str(_value_or_unknown(value)).strip()
    if text == "unavailable":
        return text

    text = text.replace("low to moderate", "light to moderate")
    text = text.replace("_", " ")
    first_sentence = text.split(". ")[0].strip()
    if first_sentence and not first_sentence.endswith("."):
        first_sentence += "."
    return first_sentence or text


def _decision_value(decision, key):
    if not isinstance(decision, dict):
        return "unavailable"
    return _value_or_unknown(decision.get(key))


def _finalized_data_note(latest_recovery_date):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if latest_recovery_date == yesterday:
        return t("report.finalized_data", date=latest_recovery_date)
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
        f"🌅 {t('report.title')}",
        f"{t('report.recovery_date')}: {_value_or_unknown(latest_recovery_date)}",
    ]
    finalized_note = _finalized_data_note(latest_recovery_date)
    if finalized_note:
        lines.append(finalized_note)

    lines.extend(
        [
            "",
            f"📊 {t('report.garmin_recovery')}",
            f"{t('report.sleep')}: {_format_float(daily_state.get('sleep_hours'), suffix='h')}",
            f"{t('report.hrv')}: {_format_int(hrv.get('hrv_value'), suffix=' ms')}",
            f"{t('report.stress')}: {_format_int(daily_state.get('stress'))}",
        ]
    )

    if daily_state.get("resting_hr") not in (None, ""):
        lines.append(
            f"{t('report.resting_hr')}: {_format_int(daily_state['resting_hr'], suffix=' bpm')}"
        )

    lines.extend(
        [
            "",
            f"{t('report.recovery_status')}:",
            _humanize_hrv_balance(hrv.get("hrv_balance")),
            "",
            f"🏃 {t('report.today_recommendation')}:",
            _humanize_token(_decision_value(decision, "decision")),
            "",
            f"{t('report.intensity')}:",
            _humanize_token(_decision_value(decision, "intensity")),
            "",
            f"{t('report.suggested_activity')}:",
            _humanize_token(_decision_value(decision, "suggested_activity")),
            "",
            f"{t('report.plan')}:",
            _humanize_plan(
                recommendation_preview.get("recommendation")
                or daily_state.get("recommendation")
            ),
            "",
            f"{t('report.why')}:",
            _shorten_rationale(rationale),
        ]
    )

    return "\n".join(lines)


def format_warning_telegram_report(reason, latest_recovery_date=""):
    lines = [
        f"⚠️ {t('warning.title')}",
        t("warning.no_recommendation"),
    ]
    if latest_recovery_date:
        lines.append(f"{t('report.recovery_date')}: {latest_recovery_date}")
    lines.append(f"{t('warning.reason')}: {_value_or_unknown(reason)}")
    return "\n".join(lines)
