import os
import time
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

from baseline import calculate_baseline
from daily_report import format_daily_report
from decision_engine import make_training_decision
from garmin_health import GARMIN_HEALTH_CSV_PATH
from garmin_health import load_garmin_health_rows, load_latest_garmin_health_with_source
from gpt_analysis import analyze_recovery
from integrations.garmindb import (
    GarminDBImportError,
    load_latest_health_data_with_metadata,
)
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
DEFAULT_GARMINDB_DIR = Path("~/HealthData/DBs").expanduser()
BODY_BATTERY_SAFE_FALLBACK = "50"
ENTRY_FIELDS = ["sleep_hours", "hrv_status", "body_battery", "resting_hr", "stress"]
OPTIONAL_ENTRY_FIELDS = {"stress"}
VALID_HRV_STATUSES = {"balanced", "low", "poor", "unbalanced"}
ENTRY_SESSIONS = {}
logger = get_logger(__name__)
UNAUTHORIZED_CHAT_MESSAGE = "Unauthorized chat."


def _metadata_metric(metadata, name):
    return metadata.get("metrics", {}).get(name, {})


def _configured_chat_id():
    load_dotenv()
    return str(os.getenv("TELEGRAM_CHAT_ID") or "").strip()


def _is_authorized_chat(chat_id):
    configured_chat_id = _configured_chat_id()
    return bool(configured_chat_id) and str(chat_id).strip() == configured_chat_id


def _authorization_error(chat_id):
    if _is_authorized_chat(chat_id):
        return None

    ENTRY_SESSIONS.pop(chat_id, None)
    logger.warning("Rejected unauthorized Telegram chat.")
    return UNAUTHORIZED_CHAT_MESSAGE


def _user_facing_hrv_balance(hrv_metric):
    balance = hrv_metric.get("hrv_balance")
    if balance == "below_baseline":
        return "Below baseline"
    if balance == "within_baseline":
        return "Within baseline"
    if balance == "above_baseline":
        return "Above baseline"

    status = str(hrv_metric.get("value") or "").strip().lower()
    if status in {"low", "poor", "unbalanced"}:
        return "Below baseline"
    if status == "balanced":
        return "Within baseline"
    if status == "high":
        return "Above baseline"
    return "Unknown"


def _freshness_message(recovery_date):
    today = date.today().isoformat()
    if recovery_date and recovery_date != today:
        return f"Latest finalized Garmin recovery data is from {recovery_date}."
    return ""


def _engine_health_dict(health_data):
    garmin_health = health_data.to_legacy_dict()
    fallback_used = False

    if garmin_health.get("body_battery") in (None, ""):
        garmin_health["body_battery"] = BODY_BATTERY_SAFE_FALLBACK
        fallback_used = True

    return garmin_health, fallback_used


def build_garmindb_today_preview(db_dir=None):
    db_dir = db_dir or os.getenv("GARMINDB_DIR") or str(DEFAULT_GARMINDB_DIR)
    health_data, metadata = load_latest_health_data_with_metadata(db_dir=db_dir)
    garmin_health, body_battery_fallback_used = _engine_health_dict(health_data)
    recovery_result = calculate_recovery(garmin_health)
    decision = make_training_decision(
        recovery_result=recovery_result,
        trend_result={"fatigue_trend": "stable", "recovery_trend": "stable"},
        garmin_health=garmin_health,
        user_profile=load_user_profile(),
    )

    rationale = decision.get("reason", "")
    if body_battery_fallback_used:
        rationale += (
            " Body Battery was unavailable, so recovery scoring used a neutral fallback."
        )

    return {
        "health_data": health_data,
        "metadata": metadata,
        "recovery_result": recovery_result,
        "decision": decision,
        "recommendation": (
            f"{decision.get('decision')} / {decision.get('intensity')} / "
            f"{decision.get('suggested_activity')}"
        ),
        "rationale": rationale,
    }


def format_garmindb_today_response(preview):
    health_data = preview["health_data"]
    metadata = preview["metadata"]
    hrv_metric = _metadata_metric(metadata, "hrv_status")
    recovery_date = metadata.get("source_date", health_data.date)
    freshness_message = _freshness_message(recovery_date)
    freshness_section = f"{freshness_message}\n" if freshness_message else ""
    stress_section = (
        f"stress={health_data.stress}\n"
        if health_data.stress not in (None, "")
        else ""
    )

    return (
        "Today Recommendation\n\n"
        f"{freshness_section}"
        f"latest_recovery_date={recovery_date}\n"
        f"sleep_hours={health_data.sleep_hours}\n"
        f"hrv_value={hrv_metric.get('hrv_value', '')}\n"
        f"hrv_5min_high={hrv_metric.get('hrv_5min_high', '')}\n"
        f"hrv_balance={_user_facing_hrv_balance(hrv_metric)}\n"
        f"resting_hr={health_data.resting_hr}\n"
        f"{stress_section}"
        f"recommendation={preview['recommendation']}\n"
        f"rationale={preview['rationale']}"
    )


def build_garmindb_today_response():
    preview = build_garmindb_today_preview()
    return format_garmindb_today_response(preview)


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
        "/weekly - Generate the weekly adaptive training plan\n"
        "/entry - Enter today's Garmin health data\n"
        "/cancel - Cancel the current entry flow"
    )


def _entry_prompt(field):
    prompts = {
        "sleep_hours": "Enter sleep_hours (0-24, decimal allowed):",
        "hrv_status": "Enter hrv_status (balanced, low, poor, unbalanced):",
        "body_battery": "Enter body_battery (0-100):",
        "resting_hr": "Enter resting_hr (20-120):",
        "stress": "Enter stress (optional, send '-' to skip):",
    }
    return prompts[field]


def _validate_float(value, min_value, max_value, label):
    try:
        parsed_value = float(value)
    except (TypeError, ValueError):
        return None, f"{label} must be a number from {min_value} to {max_value}."

    if parsed_value < min_value or parsed_value > max_value:
        return None, f"{label} must be a number from {min_value} to {max_value}."

    return str(parsed_value), None


def _validate_int(value, min_value, max_value, label):
    try:
        parsed_value = int(value)
    except (TypeError, ValueError):
        return None, f"{label} must be a whole number from {min_value} to {max_value}."

    if str(value).strip() != str(parsed_value):
        return None, f"{label} must be a whole number from {min_value} to {max_value}."

    if parsed_value < min_value or parsed_value > max_value:
        return None, f"{label} must be a whole number from {min_value} to {max_value}."

    return str(parsed_value), None


def validate_entry_field(field, value):
    value = str(value or "").strip()

    if field in OPTIONAL_ENTRY_FIELDS and value in {"", "-"}:
        return "", None

    if not value:
        return None, f"{field} is required."

    if field == "sleep_hours":
        return _validate_float(value, 0, 24, field)

    if field == "hrv_status":
        normalized_value = value.lower()
        if normalized_value not in VALID_HRV_STATUSES:
            allowed_values = ", ".join(sorted(VALID_HRV_STATUSES))
            return None, f"hrv_status must be one of {allowed_values}."
        return normalized_value, None

    if field == "body_battery":
        return _validate_int(value, 0, 100, field)

    if field == "resting_hr":
        return _validate_int(value, 20, 120, field)

    if field == "stress":
        return _validate_int(value, 0, 100, field)

    return None, f"Unknown field: {field}"


def _read_garmin_csv_rows(path):
    if not path.exists():
        return [], ["date", "sleep_hours", "hrv_status", "body_battery", "resting_hr"]

    import csv

    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        return list(reader), list(reader.fieldnames or [])


def save_telegram_entry(entry, csv_path=GARMIN_HEALTH_CSV_PATH):
    import csv

    rows, fieldnames = _read_garmin_csv_rows(csv_path)
    for field in ["date", "sleep_hours", "hrv_status", "body_battery", "resting_hr"]:
        if field not in fieldnames:
            fieldnames.append(field)

    if entry.get("stress") not in (None, "") and "stress" not in fieldnames:
        fieldnames.append("stress")

    existing_index = next(
        (index for index, row in enumerate(rows) if row.get("date") == entry["date"]),
        None,
    )

    if existing_index is None:
        rows.append(entry)
    else:
        rows[existing_index].update(entry)

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _start_entry_flow(chat_id):
    today = date.today().isoformat()
    ENTRY_SESSIONS[chat_id] = {
        "date": today,
        "field_index": 0,
        "entry": {"date": today},
    }
    return (
        f"Starting Garmin entry for {today}.\n"
        "Send /cancel anytime to stop.\n\n"
        f"{_entry_prompt(ENTRY_FIELDS[0])}"
    )


def _complete_entry_flow(chat_id, session):
    entry = session["entry"]
    save_telegram_entry(entry)
    ENTRY_SESSIONS.pop(chat_id, None)

    try:
        recommendation = build_recommendation_context()["daily_report"]
        return (
            "Garmin health entry saved.\n\n"
            "Today's recommendation:\n\n"
            f"{recommendation}"
        )
    except Exception as error:
        logger.exception("Failed to generate recommendation after Telegram entry")
        return f"Garmin health entry saved, but recommendation failed: {error}"


def _handle_entry_response(chat_id, text):
    session = ENTRY_SESSIONS.get(chat_id)
    field = ENTRY_FIELDS[session["field_index"]]
    parsed_value, error = validate_entry_field(field, text)

    if error:
        return f"{error}\n\n{_entry_prompt(field)}"

    if parsed_value != "":
        session["entry"][field] = parsed_value

    session["field_index"] += 1
    if session["field_index"] >= len(ENTRY_FIELDS):
        return _complete_entry_flow(chat_id, session)

    next_field = ENTRY_FIELDS[session["field_index"]]
    return _entry_prompt(next_field)


def handle_command(text, chat_id=None):
    authorization_error = _authorization_error(chat_id)
    if authorization_error:
        return authorization_error

    command = (text or "").strip().split()[0].lower()

    if command == "/start":
        return (
            "Welcome to stramin.\n\n"
            "Garmin CSV is the primary health data source. "
            "Use /entry to add today's metrics, /today for today's recommendation, "
            "or /weekly for the weekly plan."
        )

    if command == "/help":
        return help_text()

    if command == "/today":
        load_dotenv()
        try:
            return build_garmindb_today_response()
        except GarminDBImportError as error:
            logger.warning("GarminDB skipped for /today: %s", error)
        except Exception as error:
            logger.warning("GarminDB skipped for /today: %s", error)

        try:
            return build_recommendation_context()["daily_report"]
        except Exception as error:
            logger.exception("Failed to generate /today report")
            return (
                f"Could not generate today's recommendation: {error}\n"
                "You can use /entry to add today's Garmin metrics manually."
            )

    if command == "/weekly":
        try:
            return build_recommendation_context(include_gpt=False)["weekly_report"]
        except Exception as error:
            logger.exception("Failed to generate /weekly report")
            return f"Could not generate weekly plan: {error}"

    if command == "/entry":
        if chat_id is None:
            return "Entry flow requires a Telegram chat."
        return _start_entry_flow(chat_id)

    if command == "/cancel":
        if chat_id is not None and chat_id in ENTRY_SESSIONS:
            ENTRY_SESSIONS.pop(chat_id, None)
            return "Entry canceled."
        return "No active entry flow to cancel."

    return "Unknown command. Use /help to see available commands."


def handle_message(chat_id, text):
    text = text or ""
    authorization_error = _authorization_error(chat_id)
    if authorization_error:
        return authorization_error

    if text.strip().lower() == "/cancel":
        return handle_command(text, chat_id=chat_id)

    if chat_id in ENTRY_SESSIONS and not text.startswith("/"):
        return _handle_entry_response(chat_id, text)

    if text.startswith("/"):
        return handle_command(text, chat_id=chat_id)

    return "Send /help to see available commands."


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

                if not chat_id or not text:
                    continue

                send_message(token, chat_id, handle_message(chat_id, text))
        except requests.RequestException as error:
            logger.warning("Telegram API unavailable: %s", error)
            time.sleep(5)
        except Exception as error:
            logger.exception("Telegram bot error: %s", error)
            time.sleep(5)


if __name__ == "__main__":
    run_bot()
