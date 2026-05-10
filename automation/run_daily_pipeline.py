import argparse

from build_daily_state import build_daily_state
from common import DEFAULT_DB_DIR, DEFAULT_LOG_DIR, DEFAULT_STATE_PATH
from common import get_file_logger
from sync_garmindb import sync_garmindb
from validate_health_data import validate_garmindb

from integrations.garmindb import GarminDBImportError


def run_daily_pipeline(
    db_dir=DEFAULT_DB_DIR,
    output=DEFAULT_STATE_PATH,
    log_dir=DEFAULT_LOG_DIR,
    allow_stale=False,
):
    logger = get_file_logger("daily-pipeline", log_dir)
    logger.info("Daily pipeline started")

    sync_result = sync_garmindb(log_dir=log_dir)
    validation = validate_garmindb(
        db_dir=db_dir,
        allow_stale=allow_stale,
        log_dir=log_dir,
    )

    if validation.get("is_stale") and not allow_stale:
        raise GarminDBImportError("Stale data blocked Telegram publish")

    state = build_daily_state(db_dir=db_dir, output=output, log_dir=log_dir)
    state["sync"] = sync_result
    state["validation"] = validation
    logger.info("Daily pipeline completed without Telegram publish")

    return {
        "status": "ready",
        "telegram_sent": False,
        "telegram_reason": "Telegram publish is gated; no message sent by skeleton.",
        "state": state,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Run Stramin v4 daily pipeline skeleton.")
    parser.add_argument("--db-dir", default=str(DEFAULT_DB_DIR))
    parser.add_argument("--output", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument("--allow-stale", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        result = run_daily_pipeline(
            db_dir=args.db_dir,
            output=args.output,
            log_dir=args.log_dir,
            allow_stale=args.allow_stale,
        )
    except GarminDBImportError as error:
        print(f"Daily pipeline failed: {error}")
        return 1

    print(
        "Daily pipeline ready: "
        f"latest_recovery_date={result['state']['latest_recovery_date']}; "
        "telegram_sent=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

