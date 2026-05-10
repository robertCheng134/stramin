from reports.telegram_report import format_daily_telegram_report
from reports.telegram_report import format_warning_telegram_report


def test_daily_telegram_report_includes_key_fields():
    message = format_daily_telegram_report(
        {
            "latest_recovery_date": "2026-05-09",
            "sleep_hours": "7.0",
            "hrv": {
                "hrv_value": "42",
                "hrv_unit": "ms",
                "hrv_balance": "within_baseline",
            },
            "stress": "20",
            "resting_hr": "58",
            "recommendation": "train / normal / walking",
            "rationale": "Ready.",
            "decision": {
                "decision": "train",
                "intensity": "normal",
                "suggested_activity": "walking",
            },
        }
    )

    assert "Stramin Daily Report" in message
    assert "latest_recovery_date: 2026-05-09" in message
    assert "Latest finalized Garmin recovery data is from 2026-05-09." in message
    assert "sleep_hours: 7.0" in message
    assert "hrv: 42 ms" in message
    assert "stress: 20" in message
    assert "resting_hr: 58" in message
    assert "decision: train" in message
    assert "intensity: normal" in message
    assert "suggested_activity: walking" in message
    assert "rationale: Ready." in message


def test_warning_telegram_report_does_not_include_recommendation():
    message = format_warning_telegram_report(
        "GarminDB validation failed",
        latest_recovery_date="2026-05-08",
    )

    assert "Stramin Daily Report Delayed" in message
    assert "No training recommendation was sent." in message
    assert "latest_recovery_date: 2026-05-08" in message
    assert "Recommendation\n" not in message
