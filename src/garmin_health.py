import csv
from pathlib import Path


REQUIRED_FIELDS = [
    "date",
    "sleep_hours",
    "hrv_status",
    "body_battery",
    "resting_hr",
    "stress",
]

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

        rows = []
        for row in reader:
            rows.append({field: row.get(field, "").strip() for field in REQUIRED_FIELDS})

    if not rows:
        raise ValueError("Garmin health CSV has no data rows.")

    return rows


def load_latest_garmin_health(csv_path=None):
    rows = load_garmin_health_rows(csv_path)
    return sorted(rows, key=lambda row: row["date"])[-1]


def load_latest_garmin_health_with_source(csv_path=None):
    source_info = resolve_garmin_health_csv(csv_path)
    rows = load_garmin_health_rows(source_info["path"])
    return sorted(rows, key=lambda row: row["date"])[-1], source_info
