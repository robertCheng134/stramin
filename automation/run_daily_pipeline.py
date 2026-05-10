import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from build_daily_state import build_daily_state
from common import DEFAULT_DB_DIR, DEFAULT_LOG_DIR, DEFAULT_NOTIFICATION_STATE_PATH
from common import DEFAULT_STATE_PATH, get_file_logger, now_iso, today_iso
from common import write_json_atomic
from sync_garmindb import sync_garmindb
from validate_health_data import validate_garmindb

from integrations.garmindb import GarminDBImportError


DEFAULT_DAILY_REPORT_TIME = os.getenv("STRAMIN_DAILY_REPORT_TIME", "09:00")
DEFAULT_RETRY_INTERVAL_MINUTES = int(
    os.getenv("STRAMIN_RETRY_INTERVAL_MINUTES", "5")
)
DEFAULT_RETRY_CUTOFF_TIME = os.getenv("STRAMIN_RETRY_CUTOFF_TIME", "11:00")


def _parse_clock_time(value):
    return datetime.strptime(value, "%H:%M").time()


def _is_after_cutoff(current_time, cutoff_time):
    return current_time >= _parse_clock_time(cutoff_time)


def _load_notification_state(path):
    state_path = path.expanduser()
    if not state_path.exists():
        return {}
    with state_path.open("r", encoding="utf-8") as state_file:
        return json.load(state_file)


def _notification_state_for_today(path, current_date):
    state = _load_notification_state(path)
    if state.get("date") != current_date:
        return {
            "date": current_date,
            "telegram_sent": False,
            "sent_at": "",
            "last_attempt_at": "",
            "retry_count": 0,
            "final_failure_sent": False,
        }
    return state


def _save_notification_state(path, state):
    return write_json_atomic(path.expanduser(), state)


def run_daily_pipeline(
    db_dir=DEFAULT_DB_DIR,
    output=DEFAULT_STATE_PATH,
    log_dir=DEFAULT_LOG_DIR,
    notification_state_path=DEFAULT_NOTIFICATION_STATE_PATH,
    allow_stale=False,
    dry_run=False,
    daily_report_time=DEFAULT_DAILY_REPORT_TIME,
    retry_interval_minutes=DEFAULT_RETRY_INTERVAL_MINUTES,
    cutoff_time=DEFAULT_RETRY_CUTOFF_TIME,
    current_datetime=None,
):
    logger = get_file_logger("pipeline", log_dir)
    logger.info(
        "Daily pipeline started dry_run=%s report_time=%s cutoff_time=%s",
        dry_run,
        daily_report_time,
        cutoff_time,
    )
    current_datetime = current_datetime or datetime.now().astimezone()
    current_date = current_datetime.date().isoformat()
    current_time = current_datetime.time()
    notification_state_path = Path(notification_state_path).expanduser()
    notification_state = _notification_state_for_today(
        notification_state_path,
        current_date,
    )

    if notification_state.get("telegram_sent"):
        logger.info("Daily report already sent for %s; no-op", current_date)
        return {
            "status": "already_sent",
            "dry_run": dry_run,
            "daily_report_time": daily_report_time,
            "telegram_sent": False,
            "telegram_reason": "Daily report already sent for today.",
            "notification_state": notification_state,
        }

    sync_result = sync_garmindb(log_dir=log_dir)
    notification_state["last_attempt_at"] = now_iso()

    try:
        validation = validate_garmindb(
            db_dir=db_dir,
            allow_stale=allow_stale,
            log_dir=log_dir,
        )
    except GarminDBImportError as error:
        notification_state["retry_count"] = int(
            notification_state.get("retry_count", 0)
        ) + 1
        after_cutoff = _is_after_cutoff(current_time, cutoff_time)

        if after_cutoff:
            logger.error("Validation failed after cutoff: %s", error)
            if not dry_run:
                _save_notification_state(notification_state_path, notification_state)
            return {
                "status": "final_failure",
                "retryable": False,
                "dry_run": dry_run,
                "daily_report_time": daily_report_time,
                "telegram_sent": False,
                "telegram_reason": (
                    "Validation failed after cutoff; no training recommendation sent."
                ),
                "validation_error": str(error),
                "notification_state": notification_state,
            }

        logger.warning(
            "Validation failed before cutoff; retry in %s minutes: %s",
            retry_interval_minutes,
            error,
        )
        if not dry_run:
            _save_notification_state(notification_state_path, notification_state)
        return {
            "status": "retryable",
            "retryable": True,
            "retry_interval_minutes": retry_interval_minutes,
            "dry_run": dry_run,
            "daily_report_time": daily_report_time,
            "telegram_sent": False,
            "telegram_reason": (
                "Validation failed before cutoff; no training recommendation sent."
            ),
            "validation_error": str(error),
            "notification_state": notification_state,
        }

    if validation.get("is_stale") and not allow_stale:
        raise GarminDBImportError("Stale data blocked Telegram publish")

    state = build_daily_state(db_dir=db_dir, output=output, log_dir=log_dir)
    state["sync"] = sync_result
    state["validation"] = validation
    recommendation_preview = {
        "recommendation": state.get("recommendation", ""),
        "rationale": state.get("rationale", ""),
        "decision": state.get("decision", {}),
    }
    logger.info("Recommendation preview built: %s", recommendation_preview)
    logger.info("Daily pipeline completed without Telegram publish")

    if not dry_run:
        _save_notification_state(notification_state_path, notification_state)

    return {
        "status": "ready",
        "dry_run": dry_run,
        "daily_report_time": daily_report_time,
        "telegram_sent": False,
        "telegram_reason": (
            "Dry run enabled; no Telegram message sent."
            if dry_run
            else "Telegram auto-send is disabled for v4 local execution."
        ),
        "recommendation_preview": recommendation_preview,
        "notification_state": notification_state,
        "state": state,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Run Stramin v4 daily pipeline skeleton.")
    parser.add_argument("--db-dir", default=str(DEFAULT_DB_DIR))
    parser.add_argument("--output", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument(
        "--notification-state",
        default=str(DEFAULT_NOTIFICATION_STATE_PATH),
        help="Path to notification state JSON.",
    )
    parser.add_argument("--allow-stale", action="store_true")
    parser.add_argument("--daily-report-time", default=DEFAULT_DAILY_REPORT_TIME)
    parser.add_argument("--cutoff-time", default=DEFAULT_RETRY_CUTOFF_TIME)
    parser.add_argument(
        "--retry-interval-minutes",
        type=int,
        default=DEFAULT_RETRY_INTERVAL_MINUTES,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run validation and state generation without sending Telegram messages.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        result = run_daily_pipeline(
            db_dir=args.db_dir,
            output=args.output,
            log_dir=args.log_dir,
            notification_state_path=args.notification_state,
            allow_stale=args.allow_stale,
            dry_run=args.dry_run,
            daily_report_time=args.daily_report_time,
            retry_interval_minutes=args.retry_interval_minutes,
            cutoff_time=args.cutoff_time,
        )
    except GarminDBImportError as error:
        print(f"Daily pipeline failed: {error}")
        return 1

    if result["status"] == "retryable":
        print(
            "Daily pipeline retryable: "
            f"retry_in_minutes={result['retry_interval_minutes']}; "
            f"reason={result['validation_error']}"
        )
        return 2
    if result["status"] == "final_failure":
        print(f"Daily pipeline final failure: {result['validation_error']}")
        return 1
    if result["status"] == "already_sent":
        print("Daily pipeline no-op: report already sent for today")
        return 0
    print(
        "Daily pipeline ready: "
        f"latest_recovery_date={result['state']['latest_recovery_date']}; "
        "telegram_sent=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
