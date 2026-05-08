import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
DEFAULT_GARMINDB_PATH = Path("~/HealthData/DBs/garmin_monitoring.db").expanduser()

sys.path.insert(0, str(SRC_DIR))

from integrations.garmindb import (
    GarminDBImportError,
    load_latest_health_data_with_metadata,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Load the latest available GarminDB health metrics."
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_GARMINDB_PATH),
        help="Path to GarminDB SQLite database.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show GarminDB table, column, timestamp, and raw value details.",
    )
    return parser.parse_args()


def _metric(metadata, name):
    return metadata.get("metrics", {}).get(name, {})


def _print_metric(name, value, metadata):
    metric = _metric(metadata, name)
    print(f"{name}={value}")
    print(f"{name}_date={metric.get('date', '')}")
    if not value:
        print(f"{name}_reason={metric.get('reason') or 'no recent rows'}")


def _print_debug(metadata, db_path):
    print("\nDebug:")
    print(f"db_path={db_path}")
    print(f"schema={metadata.get('schema', '')}")
    print(f"tables={', '.join(metadata.get('tables', []))}")

    for name in ["sleep_hours", "hrv_status", "resting_hr", "body_battery", "stress"]:
        metric = _metric(metadata, name)
        print(f"\n{name}:")
        print(f"  table={metric.get('table', '')}")
        print(f"  column={metric.get('column', '')}")
        print(f"  latest_timestamp={metric.get('timestamp', '')}")
        print(f"  raw_value={metric.get('raw_value', '')}")
        print(f"  reason={metric.get('reason', '')}")


def main():
    args = parse_args()

    try:
        health_data, metadata = load_latest_health_data_with_metadata(args.db_path)
    except GarminDBImportError as error:
        print(f"GarminDB today flow failed: {error}")
        return 1

    print("Latest Garmin HealthData:")
    print(f"source_date={metadata.get('source_date', health_data.date)}")
    _print_metric("sleep_hours", health_data.sleep_hours, metadata)
    _print_metric("hrv_status", health_data.hrv_status, metadata)
    _print_metric("resting_hr", health_data.resting_hr, metadata)
    _print_metric("body_battery", health_data.body_battery_or_energy, metadata)
    if health_data.stress not in (None, ""):
        _print_metric("stress", health_data.stress, metadata)
    elif args.debug:
        _print_metric("stress", health_data.stress, metadata)

    if args.debug:
        _print_debug(metadata, args.db_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
