import argparse
import sys
from datetime import date
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
DEFAULT_GARMINDB_DIR = Path("~/HealthData/DBs").expanduser()

sys.path.insert(0, str(SRC_DIR))

from decision_engine import make_training_decision
from integrations.garmindb import (
    GarminDBImportError,
    load_latest_health_data_with_metadata,
)
from recovery_rules import calculate_recovery
from user_profile import load_user_profile


BODY_BATTERY_SAFE_FALLBACK = "50"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Preview today's recommendation from latest GarminDB health data."
    )
    parser.add_argument(
        "--db-dir",
        default=str(DEFAULT_GARMINDB_DIR),
        help="Path to GarminDB directory containing garmin.db and garmin_monitoring.db.",
    )
    return parser.parse_args()


def _metric(metadata, name):
    return metadata.get("metrics", {}).get(name, {})


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


def build_recommendation_preview(db_dir):
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


def print_preview(preview):
    health_data = preview["health_data"]
    metadata = preview["metadata"]
    hrv_metric = _metric(metadata, "hrv_status")
    recovery_date = metadata.get("source_date", health_data.date)
    freshness_message = _freshness_message(recovery_date)

    print("Today Recommendation Preview:")
    if freshness_message:
        print(freshness_message)
    print(f"latest_recovery_date={recovery_date}")
    print(f"sleep_hours={health_data.sleep_hours}")
    print(f"hrv_value={hrv_metric.get('hrv_value', '')}")
    print(f"hrv_5min_high={hrv_metric.get('hrv_5min_high', '')}")
    print(f"hrv_balance={_user_facing_hrv_balance(hrv_metric)}")
    print(f"resting_hr={health_data.resting_hr}")
    if health_data.stress not in (None, ""):
        print(f"stress={health_data.stress}")
    print(f"recovery_score={preview['recovery_result'].get('recovery_score')}")
    print(f"recovery_level={preview['recovery_result'].get('recovery_level')}")
    print(f"recommendation={preview['recommendation']}")
    print(f"rationale={preview['rationale']}")


def main():
    args = parse_args()

    try:
        preview = build_recommendation_preview(args.db_dir)
    except GarminDBImportError as error:
        print(f"GarminDB recommendation preview failed: {error}")
        return 1

    print_preview(preview)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
