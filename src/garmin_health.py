import csv
from datetime import datetime
from pathlib import Path


REQUIRED_FIELDS = [
    "date",
    "sleep_hours",
    "hrv_status",
    "body_battery",
    "resting_hr",
]
OPTIONAL_FIELDS = ["stress"]
VALID_HRV_STATUSES = {"balanced", "low", "poor", "unbalanced"}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GARMIN_HEALTH_CSV_PATH = DATA_DIR / "garmin_health.csv"
SAMPLE_CSV_PATH = DATA_DIR / "garmin_health_sample.csv"


def resolve_garmin_health_csv(csv_path=None):
    if csv_path:
        return {
            "path": Path(csv_path),
            "source": "custom",
            "is_sample": False,
            "message": None,
        }

    if GARMIN_HEALTH_CSV_PATH.exists():
        return {
            "path": GARMIN_HEALTH_CSV_PATH,
            "source": "real",
            "is_sample": False,
            "message": None,
        }

    return {
        "path": SAMPLE_CSV_PATH,
        "source": "sample",
        "is_sample": True,
        "message": (
            f"{GARMIN_HEALTH_CSV_PATH} not found. "
            f"Using sample data from {SAMPLE_CSV_PATH}."
        ),
    }


def _validate_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return False
    return True


def _validate_float_range(value, min_value, max_value):
    try:
        parsed_value = float(value)
    except (TypeError, ValueError):
        return False
    return min_value <= parsed_value <= max_value


def _validate_int_range(value, min_value, max_value):
    try:
        parsed_value = int(value)
    except (TypeError, ValueError):
        return False
    return str(value).strip() == str(parsed_value) and min_value <= parsed_value <= max_value


def _validate_garmin_row(row):
    if not _validate_date(row.get("date")):
        return "date must be YYYY-MM-DD"

    if not _validate_float_range(row.get("sleep_hours"), 0, 24):
        return "sleep_hours must be a 0~24 float"

    hrv_status = str(row.get("hrv_status") or "").strip().lower()
    if hrv_status not in VALID_HRV_STATUSES:
        return "hrv_status must be balanced/low/poor/unbalanced"

    if not _validate_int_range(row.get("body_battery"), 0, 100):
        return "body_battery must be a 0~100 int"

    if not _validate_int_range(row.get("resting_hr"), 20, 120):
        return "resting_hr must be a 20~120 int"

    return None


def load_garmin_health_rows(csv_path=None):
    source_info = resolve_garmin_health_csv(csv_path)
    path = source_info["path"]

    if not path.exists():
        raise FileNotFoundError(f"Garmin health CSV not found: {path}")

    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        missing_fields = [
            field for field in REQUIRED_FIELDS if field not in (reader.fieldnames or [])
        ]
        if missing_fields:
            raise ValueError(
                "Garmin health CSV is missing required fields: "
                + ", ".join(missing_fields)
            )

        fields = REQUIRED_FIELDS + [
            field for field in OPTIONAL_FIELDS if field in (reader.fieldnames or [])
        ]

        rows = []
        for row in reader:
            normalized_row = {
                field: row.get(field, "").strip() for field in fields
            }
            normalized_row["hrv_status"] = normalized_row["hrv_status"].lower()

            invalid_reason = _validate_garmin_row(normalized_row)
            if invalid_reason:
                print(f"Skipping invalid Garmin row: {invalid_reason}")
                continue

            rows.append(normalized_row)

    if not rows:
        raise ValueError("No valid Garmin health data found.")

    return rows


def load_latest_garmin_health(csv_path=None):
    rows = load_garmin_health_rows(csv_path)
    return sorted(rows, key=lambda row: row["date"])[-1]


def load_latest_garmin_health_with_source(csv_path=None):
    source_info = resolve_garmin_health_csv(csv_path)
    rows = load_garmin_health_rows(source_info["path"])
    return sorted(rows, key=lambda row: row["date"])[-1], source_info
