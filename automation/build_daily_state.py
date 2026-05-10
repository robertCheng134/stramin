import argparse

from common import DEFAULT_DB_DIR, DEFAULT_LOG_DIR, DEFAULT_STATE_PATH, get_file_logger
from common import now_iso, write_json_atomic

from scripts.preview_garmindb_recommendation import build_recommendation_preview


def _metric(metadata, name):
    return metadata.get("metrics", {}).get(name, {})


def build_daily_state(db_dir=DEFAULT_DB_DIR, output=DEFAULT_STATE_PATH, log_dir=DEFAULT_LOG_DIR):
    logger = get_file_logger("daily-state", log_dir)
    preview = build_recommendation_preview(db_dir)
    health_data = preview["health_data"]
    metadata = preview["metadata"]
    hrv_metric = _metric(metadata, "hrv_status")

    state = {
        "generated_at": now_iso(),
        "latest_recovery_date": metadata.get("source_date", health_data.date),
        "validation_status": "ready",
        "metrics": {
            "sleep_hours": health_data.sleep_hours,
            "hrv_value": hrv_metric.get("hrv_value", ""),
            "hrv_5min_high": hrv_metric.get("hrv_5min_high", ""),
            "hrv_balance": hrv_metric.get("hrv_balance", ""),
            "resting_hr": health_data.resting_hr,
            "stress": health_data.stress,
        },
        "recovery": preview["recovery_result"],
        "decision": preview["decision"],
        "recommendation": preview["recommendation"],
        "rationale": preview["rationale"],
    }

    path = write_json_atomic(output, state)
    logger.info("Daily state written atomically: %s", path)
    return state


def parse_args():
    parser = argparse.ArgumentParser(description="Build atomic Stramin daily state.")
    parser.add_argument("--db-dir", default=str(DEFAULT_DB_DIR))
    parser.add_argument("--output", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    return parser.parse_args()


def main():
    args = parse_args()
    state = build_daily_state(
        db_dir=args.db_dir,
        output=args.output,
        log_dir=args.log_dir,
    )
    print(f"daily_state written: latest_recovery_date={state['latest_recovery_date']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

