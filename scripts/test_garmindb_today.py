import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
DEFAULT_GARMINDB_PATH = Path("~/HealthData/DBs/garmin_monitoring.db").expanduser()

sys.path.insert(0, str(SRC_DIR))

from integrations.garmindb import GarminDBImportError, load_latest_health_data


def parse_args():
    parser = argparse.ArgumentParser(
        description="Load the latest available GarminDB health metrics."
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_GARMINDB_PATH),
        help="Path to GarminDB SQLite database.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        health_data = load_latest_health_data(args.db_path)
    except GarminDBImportError as error:
        print(f"GarminDB today flow failed: {error}")
        return 1

    print("Latest Garmin HealthData:")
    print(f"sleep_hours={health_data.sleep_hours}")
    print(f"hrv_status={health_data.hrv_status}")
    print(f"resting_hr={health_data.resting_hr}")
    print(f"body_battery={health_data.body_battery_or_energy}")
    if health_data.stress not in (None, ""):
        print(f"stress={health_data.stress}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
