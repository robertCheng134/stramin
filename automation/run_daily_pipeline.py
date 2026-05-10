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
    dry_run=False,
):
    logger = get_file_logger("pipeline", log_dir)
    logger.info("Daily pipeline started dry_run=%s", dry_run)

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
    recommendation_preview = {
        "recommendation": state.get("recommendation", ""),
        "rationale": state.get("rationale", ""),
        "decision": state.get("decision", {}),
    }
    logger.info("Recommendation preview built: %s", recommendation_preview)
    logger.info("Daily pipeline completed without Telegram publish")

    return {
        "status": "ready",
        "dry_run": dry_run,
        "telegram_sent": False,
        "telegram_reason": (
            "Dry run enabled; no Telegram message sent."
            if dry_run
            else "Telegram auto-send is disabled for v4 local execution."
        ),
        "recommendation_preview": recommendation_preview,
        "state": state,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Run Stramin v4 daily pipeline skeleton.")
    parser.add_argument("--db-dir", default=str(DEFAULT_DB_DIR))
    parser.add_argument("--output", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument("--allow-stale", action="store_true")
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
            allow_stale=args.allow_stale,
            dry_run=args.dry_run,
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
