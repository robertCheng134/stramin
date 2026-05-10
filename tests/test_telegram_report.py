from datetime import date, timedelta

from reports.telegram_report import format_daily_telegram_report
from reports.telegram_report import format_warning_telegram_report


def test_daily_telegram_report_includes_key_fields():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    message = format_daily_telegram_report(
        {
            "latest_recovery_date": yesterday,
            "sleep_hours": "7.04",
            "hrv": {
                "hrv_value": "41.7",
                "hrv_unit": "ms",
                "hrv_balance": "within_baseline",
            },
            "stress": "20.2",
            "resting_hr": "58.4",
            "recommendation": "train / normal / walking",
            "rationale": "Recovery metrics are slightly below baseline today. Keep it easy.",
            "decision": {
                "decision": "light_training",
                "intensity": "low to moderate",
                "suggested_activity": "weight_training",
            },
        }
    )

    assert "🌅 Stramin Daily Recovery" in message
    assert f"Recovery date: {yesterday}" in message
    assert f"Latest finalized Garmin recovery data is from {yesterday}." in message
    assert "Sleep: 7.0h" in message
    assert "HRV: 42 ms" in message
    assert "Stress: 20" in message
    assert "Resting HR: 58 bpm" in message
    assert "Recovery status:\nWithin baseline" in message
    assert "Today's recommendation:\nLight training" in message
    assert "Intensity:\nLight to moderate" in message
    assert "Suggested activity:\nWeight training" in message
    assert "Why:\nRecovery metrics are slightly below baseline today." in message
    assert "suggested_activity" not in message
    assert "decision:" not in message
    assert "low to moderate" not in message


def test_warning_telegram_report_does_not_include_recommendation():
    message = format_warning_telegram_report(
        "GarminDB validation failed",
        latest_recovery_date="2026-05-08",
    )

    assert "⚠️ Stramin Daily Report Delayed" in message
    assert "No training recommendation was sent." in message
    assert "Recovery date: 2026-05-08" in message
    assert "Recommendation\n" not in message
