import os
import time

import requests
from dotenv import load_dotenv

from baseline import calculate_baseline
from daily_report import format_daily_report
from decision_engine import make_training_decision
from garmin_health import load_garmin_health_rows, load_latest_garmin_health_with_source
from gpt_analysis import analyze_recovery
from logger import get_logger
from recovery_rules import calculate_recovery
from strava import fetch_recent_activities
from training_load import analyze_training_load
from trend_analysis import analyze_recent_trends
from user_profile import load_user_profile
from weekly_planner import generate_weekly_plan
from weekly_report import format_weekly_report


TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"
MAX_TELEGRAM_MESSAGE_LENGTH = 4000
logger = get_logger(__name__)


def _fetch_strava_activities_if_available():
    try:
        return fetch_recent_activities(per_page=10)
    except RuntimeError as error:
        logger.warning("Strava skipped: %s", error)
    except requests.RequestException as error:
        logger.warning("Strava skipped: %s", error)

    return None


def build_recommendation_context(include_gpt=True):
    load_dotenv()

    garmin_health, garmin_source = load_latest_garmin_health_with_source()
    garmin_rows = load_garmin_health_rows(garmin_source["path"])
    baseline = calculate_baseline(garmin_rows)
    user_profile = load_user_profile()
    recovery = calculate_recovery(garmin_health, baseline=baseline)
    trends = analyze_recent_trends(garmin_source["path"])
    strava_activities = _fetch_strava_activities_if_available()
    strava_activity = strava_activities[0] if strava_activities else None
    training_load = (
        analyze_training_load(strava_activities, user_profile=user_profile)
        if strava_activities is not None
        else None
    )
    decision = make_training_decision(
        recovery_result=recovery,
        trend_result=trends,
        garmin_health=garmin_health,
        strava_activity=strava_activity,
        user_profile=user_profile,
        training_load=training_load,
    )
    weekly_plan = generate_weekly_plan(
        recovery_result=recovery,
        trend_result=trends,
        user_profile=user_profile,
        training_load=training_load,
    )

    gpt_analysis = None
    if include_gpt and os.getenv("OPENAI_API_KEY"):
        try:
            gpt_analysis = analyze_recovery(
                garmin_health=garmin_health,
                recovery_result=recovery,
                strava_activity=strava_activity,
            )
        except Exception as error:
            logger.warning("GPT skipped: %s", error)
    elif include_gpt:
        logger.warning("GPT skipped: Missing OPENAI_API_KEY environment variable.")

    daily_report = format_daily_report(
        garmin_health=garmin_health,
        recovery_result=recovery,
        strava_activity=strava_activity,
        gpt_analysis=gpt_analysis,
        trend_analysis=trends,
        training_decision=decision,
        baseline=baseline,
        training_load=training_load,
    )
    weekly_report = format_weekly_report(weekly_plan)

    return {
        "daily_report": daily_report,
        "weekly_report": weekly_report,
    }


def help_text():
    return (
        "stramin Telegram Bot\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/help - Show available commands\n"
        "/today - Generate today's Garmin-first recovery recommendation\n"
        "/weekly - Generate the weekly adaptive training plan"
    )


def handle_command(text):
    command = (text or "").strip().split()[0].lower()

    if command == "/start":
        return (
            "Welcome to stramin.\n\n"
            "Garmin CSV is the primary health data source. "
            "Use /today for today's recommendation or /weekly for the weekly plan."
        )

    if command == "/help":
        return help_text()

    if command == "/today":
        try:
            return build_recommendation_context()["daily_report"]
        except Exception as error:
            logger.exception("Failed to generate /today report")
            return f"Could not generate today's recommendation: {error}"

    if command == "/weekly":
        try:
            return build_recommendation_context(include_gpt=False)["weekly_report"]
        except Exception as error:
            logger.exception("Failed to generate /weekly report")
            return f"Could not generate weekly plan: {error}"

    return "Unknown command. Use /help to see available commands."


def _telegram_url(token, method):
    return TELEGRAM_API_URL.format(token=token, method=method)


def send_message(token, chat_id, text):
    for start in range(0, len(text), MAX_TELEGRAM_MESSAGE_LENGTH):
        chunk = text[start : start + MAX_TELEGRAM_MESSAGE_LENGTH]
        response = requests.post(
            _telegram_url(token, "sendMessage"),
            json={"chat_id": chat_id, "text": chunk},
            timeout=30,
        )
        response.raise_for_status()


def get_updates(token, offset=None, timeout=30):
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset

    response = requests.get(
        _telegram_url(token, "getUpdates"),
        params=params,
        timeout=timeout + 10,
    )
    response.raise_for_status()
    return response.json().get("result", [])


def run_bot():
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable.")

    logger.info("Telegram bot started.")
    offset = None

    while True:
        try:
            updates = get_updates(token, offset=offset)
            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message") or {}
                chat = message.get("chat") or {}
                chat_id = chat.get("id")
                text = message.get("text", "")

                if not chat_id or not text.startswith("/"):
                    continue

                send_message(token, chat_id, handle_command(text))
        except requests.RequestException as error:
            logger.warning("Telegram API unavailable: %s", error)
            time.sleep(5)
        except Exception as error:
            logger.exception("Telegram bot error: %s", error)
            time.sleep(5)


if __name__ == "__main__":
    run_bot()
