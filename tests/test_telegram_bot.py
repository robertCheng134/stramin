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
