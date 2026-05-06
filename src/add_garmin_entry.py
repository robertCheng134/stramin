import argparse
import csv
from datetime import date, datetime

from garmin_health import GARMIN_HEALTH_CSV_PATH, REQUIRED_FIELDS


def _prompt_value(label, default=None):
    prompt = f"{label}"
    if default is not None:
        prompt += f" [{default}]"
    prompt += ": "

    value = input(prompt).strip()
    return value or default


def _load_existing_rows(path):
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        return [
            {field: row.get(field, "").strip() for field in REQUIRED_FIELDS}
            for row in reader
        ]


def _write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=REQUIRED_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _parse_args():
    parser = argparse.ArgumentParser(description="Add a Garmin health CSV entry.")
    parser.add_argument(
        "--date",
        dest="entry_date",
        default=date.today().isoformat(),
        help="Entry date in YYYY-MM-DD format. Defaults to today.",
    )
    return parser.parse_args()


def _validate_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError("date must use YYYY-MM-DD format") from error

    return value


def collect_garmin_entry(entry_date):
    return {
        "date": entry_date,
        "sleep_hours": _prompt_value("sleep_hours"),
        "hrv_status": _prompt_value("hrv_status"),
        "body_battery": _prompt_value("body_battery"),
        "resting_hr": _prompt_value("resting_hr"),
    }


def save_garmin_entry(entry, csv_path=GARMIN_HEALTH_CSV_PATH):
    rows = _load_existing_rows(csv_path)
    existing_index = next(
        (index for index, row in enumerate(rows) if row.get("date") == entry["date"]),
        None,
    )

    if existing_index is not None:
        should_overwrite = input(
            f"Entry for {entry['date']} already exists. Overwrite? [y/n]: "
        ).strip().lower()

        if should_overwrite != "y":
            print("Canceled.")
            return False

        rows[existing_index] = entry
    else:
        rows.append(entry)

    _write_rows(csv_path, rows)
    print("Garmin health entry saved.")
    return True


def main():
    args = _parse_args()
    entry_date = _validate_date(args.entry_date)

    print(f"Today's date: {entry_date}")

    entry = collect_garmin_entry(entry_date)
    save_garmin_entry(entry)


if __name__ == "__main__":
    main()
