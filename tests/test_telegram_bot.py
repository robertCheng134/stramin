import sys
from datetime import date
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import telegram_bot
from health_data import HealthData
from integrations.garmindb import GarminDBImportError


AUTHORIZED_CHAT_ID = 123
UNAUTHORIZED_CHAT_ID = 999


@pytest.fixture(autouse=True)
def telegram_auth(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", str(AUTHORIZED_CHAT_ID))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-bot-token")
    telegram_bot.ENTRY_SESSIONS.clear()


def test_start_command_returns_intro():
    response = telegram_bot.handle_command("/start", chat_id=AUTHORIZED_CHAT_ID)

    assert "Welcome to stramin" in response
    assert "/today" in response


def test_help_command_lists_commands():
    response = telegram_bot.handle_command("/help", chat_id=AUTHORIZED_CHAT_ID)

    assert "/today" in response
    assert "/weekly" in response
    assert "/entry" in response
    assert "/cancel" in response


def test_unauthorized_chat_is_rejected():
    response = telegram_bot.handle_message(UNAUTHORIZED_CHAT_ID, "/help")

    assert response == telegram_bot.UNAUTHORIZED_CHAT_MESSAGE


def test_unauthorized_chat_cannot_start_entry():
    response = telegram_bot.handle_message(UNAUTHORIZED_CHAT_ID, "/entry")

    assert response == telegram_bot.UNAUTHORIZED_CHAT_MESSAGE
    assert UNAUTHORIZED_CHAT_ID not in telegram_bot.ENTRY_SESSIONS


def test_unauthorized_chat_cannot_continue_entry(monkeypatch):
    saved_entries = []
    telegram_bot.ENTRY_SESSIONS[UNAUTHORIZED_CHAT_ID] = {
        "date": "2026-05-21",
        "field_index": 0,
        "entry": {"date": "2026-05-21"},
    }
    monkeypatch.setattr(
        telegram_bot,
        "save_telegram_entry",
        lambda entry: saved_entries.append(entry),
    )

    response = telegram_bot.handle_message(UNAUTHORIZED_CHAT_ID, "7.5")

    assert response == telegram_bot.UNAUTHORIZED_CHAT_MESSAGE
    assert saved_entries == []
    assert UNAUTHORIZED_CHAT_ID not in telegram_bot.ENTRY_SESSIONS


def test_unauthorized_response_does_not_leak_secrets(monkeypatch, capsys):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "7157240394")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "super-secret-token")

    response = telegram_bot.handle_message(UNAUTHORIZED_CHAT_ID, "/today")
    captured = capsys.readouterr()

    combined_output = response + captured.out + captured.err
    assert response == telegram_bot.UNAUTHORIZED_CHAT_MESSAGE
    assert "7157240394" not in combined_output
    assert "super-secret-token" not in combined_output


def test_today_command_uses_daily_report(monkeypatch):
    monkeypatch.setattr(
        telegram_bot,
        "build_garmindb_today_response",
        lambda: (_ for _ in ()).throw(GarminDBImportError("missing db")),
    )
    monkeypatch.setattr(
        telegram_bot,
        "build_recommendation_context",
        lambda include_gpt=True: {
            "daily_report": "Daily Recovery Report",
            "weekly_report": "Weekly Training Plan",
        },
    )

    assert (
        telegram_bot.handle_command("/today", chat_id=AUTHORIZED_CHAT_ID)
        == "Daily Recovery Report"
    )


def test_today_command_prefers_garmindb_recommendation(monkeypatch):
    called = {"csv": False}

    def fake_csv_context(include_gpt=True):
        called["csv"] = True
        return {
            "daily_report": "CSV Daily Recovery Report",
            "weekly_report": "Weekly Training Plan",
        }

    monkeypatch.setenv("GARMINDB_DIR", "/tmp/garmindb")
    monkeypatch.setattr(telegram_bot, "build_recommendation_context", fake_csv_context)
    monkeypatch.setattr(
        telegram_bot,
        "load_latest_health_data_with_metadata",
        lambda db_dir: (
            HealthData(
                date="2026-05-07",
                sleep_hours="7.5",
                hrv_status="balanced",
                body_battery_or_energy="",
                resting_hr="62",
                stress="42",
                source="garmindb",
            ),
            {
                "source_date": "2026-05-07",
                "metrics": {
                    "hrv_status": {
                        "hrv_value": "37",
                        "hrv_5min_high": "52",
                        "hrv_balance": "within_baseline",
                        "hrv_risk": "stable",
                    }
                },
            },
        ),
    )
    monkeypatch.setattr(
        telegram_bot,
        "calculate_recovery",
        lambda garmin_health: {
            "recovery_score": 80,
            "recovery_level": "good",
        },
    )
    monkeypatch.setattr(
        telegram_bot,
        "make_training_decision",
        lambda **kwargs: {
            "decision": "train",
            "intensity": "normal",
            "suggested_activity": "walking",
            "reason": "Looks ready.",
        },
    )
    monkeypatch.setattr(
        telegram_bot,
        "load_user_profile",
        lambda: {"preferred_activities": ["walking"]},
    )

    response = telegram_bot.handle_command("/today", chat_id=AUTHORIZED_CHAT_ID)

    assert "Today Recommendation" in response
    assert "latest_recovery_date=2026-05-07" in response
    assert "sleep_hours=7.5" in response
    assert "hrv_value=37" in response
    assert "hrv_5min_high=52" in response
    assert "hrv_balance=Within baseline" in response
    assert "hrv_risk" not in response
    assert "resting_hr=62" in response
    assert "stress=42" in response
    assert "recommendation=train / normal / walking" in response
    assert "rationale=Looks ready." in response
    assert "Body Battery was unavailable" in response
    assert called["csv"] is False


def test_garmindb_today_response_includes_freshness_message(monkeypatch):
    class FakeDate:
        @staticmethod
        def today():
            return date(2026, 5, 8)

    monkeypatch.setattr(telegram_bot, "date", FakeDate)
    preview = {
        "health_data": HealthData(
            date="2026-05-07",
            sleep_hours="7.5",
            hrv_status="low",
            body_battery_or_energy="50",
            resting_hr="62",
            stress="42",
            source="garmindb",
        ),
        "metadata": {
            "source_date": "2026-05-07",
            "metrics": {
                "hrv_status": {
                    "hrv_value": "31",
                    "hrv_5min_high": "52",
                    "hrv_balance": "below_baseline",
                }
            },
        },
        "recommendation": "light_training / low / walking",
        "rationale": "Take it easy.",
    }

    response = telegram_bot.format_garmindb_today_response(preview)

    assert "Latest finalized Garmin recovery data is from 2026-05-07." in response
    assert "hrv_balance=Below baseline" in response


def test_today_command_falls_back_when_garmindb_unavailable(monkeypatch):
    monkeypatch.setattr(
        telegram_bot,
        "build_garmindb_today_response",
        lambda: (_ for _ in ()).throw(GarminDBImportError("missing db")),
    )
    monkeypatch.setattr(
        telegram_bot,
        "build_recommendation_context",
        lambda include_gpt=True: {
            "daily_report": "Fallback CSV Daily Report",
            "weekly_report": "Weekly Training Plan",
        },
    )

    assert (
        telegram_bot.handle_command("/today", chat_id=AUTHORIZED_CHAT_ID)
        == "Fallback CSV Daily Report"
    )


def test_today_command_prompts_entry_when_all_sources_fail(monkeypatch):
    monkeypatch.setattr(
        telegram_bot,
        "build_garmindb_today_response",
        lambda: (_ for _ in ()).throw(GarminDBImportError("missing db")),
    )
    monkeypatch.setattr(
        telegram_bot,
        "build_recommendation_context",
        lambda include_gpt=True: (_ for _ in ()).throw(RuntimeError("no csv")),
    )

    response = telegram_bot.handle_command("/today", chat_id=AUTHORIZED_CHAT_ID)

    assert "Could not generate today's recommendation" in response
    assert "/entry" in response


def test_weekly_command_uses_weekly_report_without_gpt(monkeypatch):
    captured = {}

    def fake_context(include_gpt=True):
        captured["include_gpt"] = include_gpt
        return {
            "daily_report": "Daily Recovery Report",
            "weekly_report": "Weekly Training Plan",
        }

    monkeypatch.setattr(telegram_bot, "build_recommendation_context", fake_context)

    assert (
        telegram_bot.handle_command("/weekly", chat_id=AUTHORIZED_CHAT_ID)
        == "Weekly Training Plan"
    )
    assert captured["include_gpt"] is False


def test_unknown_command_returns_help_hint():
    response = telegram_bot.handle_command("/wat", chat_id=AUTHORIZED_CHAT_ID)

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

    assert "sleep_hours" in telegram_bot.handle_message(AUTHORIZED_CHAT_ID, "/entry")
    assert "hrv_status" in telegram_bot.handle_message(AUTHORIZED_CHAT_ID, "7.5")
    assert "body_battery" in telegram_bot.handle_message(
        AUTHORIZED_CHAT_ID,
        "balanced",
    )
    assert "resting_hr" in telegram_bot.handle_message(AUTHORIZED_CHAT_ID, "80")
    assert "stress" in telegram_bot.handle_message(AUTHORIZED_CHAT_ID, "55")
    response = telegram_bot.handle_message(AUTHORIZED_CHAT_ID, "-")

    assert "Garmin health entry saved" in response
    assert "Daily Recovery Report" in response
    assert saved_entry["sleep_hours"] == "7.5"
    assert saved_entry["hrv_status"] == "balanced"
    assert saved_entry["body_battery"] == "80"
    assert saved_entry["resting_hr"] == "55"
    assert "stress" not in saved_entry
    assert AUTHORIZED_CHAT_ID not in telegram_bot.ENTRY_SESSIONS


def test_entry_flow_reprompts_after_invalid_value():
    assert "sleep_hours" in telegram_bot.handle_message(AUTHORIZED_CHAT_ID, "/entry")
    response = telegram_bot.handle_message(AUTHORIZED_CHAT_ID, "df")

    assert "sleep_hours must be a number" in response
    assert "Enter sleep_hours" in response
    assert telegram_bot.ENTRY_SESSIONS[AUTHORIZED_CHAT_ID]["field_index"] == 0


def test_cancel_clears_entry_flow():
    telegram_bot.handle_message(AUTHORIZED_CHAT_ID, "/entry")
    response = telegram_bot.handle_message(AUTHORIZED_CHAT_ID, "/cancel")

    assert response == "Entry canceled."
    assert AUTHORIZED_CHAT_ID not in telegram_bot.ENTRY_SESSIONS


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
