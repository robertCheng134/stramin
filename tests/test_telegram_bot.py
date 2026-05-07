import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import telegram_bot


def test_start_command_returns_intro():
    response = telegram_bot.handle_command("/start")

    assert "Welcome to stramin" in response
    assert "/today" in response


def test_help_command_lists_commands():
    response = telegram_bot.handle_command("/help")

    assert "/today" in response
    assert "/weekly" in response
    assert "/entry" in response
    assert "/cancel" in response


def test_today_command_uses_daily_report(monkeypatch):
    monkeypatch.setattr(
        telegram_bot,
        "build_recommendation_context",
        lambda include_gpt=True: {
            "daily_report": "Daily Recovery Report",
            "weekly_report": "Weekly Training Plan",
        },
    )

    assert telegram_bot.handle_command("/today") == "Daily Recovery Report"


def test_weekly_command_uses_weekly_report_without_gpt(monkeypatch):
    captured = {}

    def fake_context(include_gpt=True):
        captured["include_gpt"] = include_gpt
        return {
            "daily_report": "Daily Recovery Report",
            "weekly_report": "Weekly Training Plan",
        }

    monkeypatch.setattr(telegram_bot, "build_recommendation_context", fake_context)

    assert telegram_bot.handle_command("/weekly") == "Weekly Training Plan"
    assert captured["include_gpt"] is False


def test_unknown_command_returns_help_hint():
    response = telegram_bot.handle_command("/wat")

    assert "Unknown command" in response


def test_validate_entry_field_rejects_invalid_values():
    _, sleep_error = telegram_bot.validate_entry_field("sleep_hours", "asdf")
    _, hrv_error = telegram_bot.validate_entry_field("hrv_status", "d")
    _, battery_error = telegram_bot.validate_entry_field("body_battery", "101")
    _, resting_hr_error = telegram_bot.validate_entry_field("resting_hr", "10")

    assert "sleep_hours must be a number" in sleep_error
    assert "hrv_status must be one of" in hrv_error
    assert "body_battery must be a whole number" in battery_error
    assert "resting_hr must be a whole number" in resting_hr_error


def test_entry_flow_collects_values_and_saves(monkeypatch):
    telegram_bot.ENTRY_SESSIONS.clear()
    saved_entry = {}

    def fake_save(entry):
        saved_entry.update(entry)

    monkeypatch.setattr(telegram_bot, "save_telegram_entry", fake_save)
    monkeypatch.setattr(
        telegram_bot,
        "build_recommendation_context",
        lambda include_gpt=True: {
            "daily_report": "Daily Recovery Report",
            "weekly_report": "Weekly Training Plan",
        },
    )

    assert "sleep_hours" in telegram_bot.handle_message(123, "/entry")
    assert "hrv_status" in telegram_bot.handle_message(123, "7.5")
    assert "body_battery" in telegram_bot.handle_message(123, "balanced")
    assert "resting_hr" in telegram_bot.handle_message(123, "80")
    assert "stress" in telegram_bot.handle_message(123, "55")
    response = telegram_bot.handle_message(123, "-")

    assert "Garmin health entry saved" in response
    assert "Daily Recovery Report" in response
    assert saved_entry["sleep_hours"] == "7.5"
    assert saved_entry["hrv_status"] == "balanced"
    assert saved_entry["body_battery"] == "80"
    assert saved_entry["resting_hr"] == "55"
    assert "stress" not in saved_entry
    assert 123 not in telegram_bot.ENTRY_SESSIONS


def test_entry_flow_reprompts_after_invalid_value():
    telegram_bot.ENTRY_SESSIONS.clear()

    assert "sleep_hours" in telegram_bot.handle_message(456, "/entry")
    response = telegram_bot.handle_message(456, "df")

    assert "sleep_hours must be a number" in response
    assert "Enter sleep_hours" in response
    assert telegram_bot.ENTRY_SESSIONS[456]["field_index"] == 0


def test_cancel_clears_entry_flow():
    telegram_bot.ENTRY_SESSIONS.clear()

    telegram_bot.handle_message(789, "/entry")
    response = telegram_bot.handle_message(789, "/cancel")

    assert response == "Entry canceled."
    assert 789 not in telegram_bot.ENTRY_SESSIONS


def test_save_telegram_entry_writes_and_updates_same_date(tmp_path):
    csv_path = tmp_path / "garmin_health.csv"
    first_entry = {
        "date": "2026-05-07",
        "sleep_hours": "7.0",
        "hrv_status": "balanced",
        "body_battery": "70",
        "resting_hr": "58",
    }
    second_entry = {
        "date": "2026-05-07",
        "sleep_hours": "8.0",
        "hrv_status": "low",
        "body_battery": "45",
        "resting_hr": "62",
        "stress": "35",
    }

    telegram_bot.save_telegram_entry(first_entry, csv_path=csv_path)
    telegram_bot.save_telegram_entry(second_entry, csv_path=csv_path)

    contents = csv_path.read_text(encoding="utf-8")
    assert contents.count("2026-05-07") == 1
    assert "stress" in contents
    assert "8.0,low,45,62,35" in contents
