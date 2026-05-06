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

DEFAULT_CSV_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "garmin_health_sample.csv"
)


def load_garmin_health_rows(csv_path=DEFAULT_CSV_PATH):
    path = Path(csv_path)
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


def load_latest_garmin_health(csv_path=DEFAULT_CSV_PATH):
    rows = load_garmin_health_rows(csv_path)
    return sorted(rows, key=lambda row: row["date"])[-1]
