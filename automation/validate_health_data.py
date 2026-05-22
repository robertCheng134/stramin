import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

from common import DEFAULT_DB_DIR, DEFAULT_LOG_DIR, get_file_logger, today_iso

from integrations.garmindb import GarminDBImportError


OBSERVED_TABLES = ["hrv", "sleep", "stress", "daily_summary"]
REQUIRED_NON_EMPTY_TABLES = ["daily_summary"]


def _table_count(db_path, table):
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(f'SELECT count(*) FROM "{table}"')
        return cursor.fetchone()[0]


def _has_table(db_path, table):
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        )
        return cursor.fetchone() is not None


def _latest_daily_summary_day(db_path):
    with sqlite3.connect(db_path) as connection:
        columns = [
            row[1]
            for row in connection.execute('PRAGMA table_info("daily_summary")').fetchall()
        ]
        if "day" not in columns:
            raise GarminDBImportError("daily_summary table is missing day column")
        cursor = connection.execute(
            'SELECT date(day) AS day FROM daily_summary ORDER BY date(day) DESC LIMIT 1'
        )
        row = cursor.fetchone()
        return row[0] if row else ""


def _fail_validation(logger, message):
    full_message = f"GarminDB validation failed: {message}"
    logger.error(full_message)
    raise GarminDBImportError(full_message)


def _days_old(latest_date, current_date):
    latest = datetime.strptime(latest_date, "%Y-%m-%d").date()
    current = datetime.strptime(current_date, "%Y-%m-%d").date()
    return (current - latest).days


def validate_garmindb(db_dir=DEFAULT_DB_DIR, allow_stale=False, log_dir=DEFAULT_LOG_DIR):
    logger = get_file_logger("pipeline", log_dir)
    db_dir = Path(db_dir).expanduser()
    garmin_db = db_dir / "garmin.db"

    if not garmin_db.exists():
        _fail_validation(logger, f"missing GarminDB database at {garmin_db}")

    table_counts = {}
    for table in OBSERVED_TABLES:
        try:
            if _has_table(garmin_db, table):
                table_counts[table] = _table_count(garmin_db, table)
            else:
                table_counts[table] = 0
        except sqlite3.Error as error:
            _fail_validation(logger, f"table {table} is unreadable: {error}")

    for table in REQUIRED_NON_EMPTY_TABLES:
        if table_counts.get(table, 0) <= 0:
            _fail_validation(logger, f"table {table} is empty")

    try:
        latest_date = _latest_daily_summary_day(garmin_db)
    except (sqlite3.Error, GarminDBImportError) as error:
        _fail_validation(logger, f"daily_summary.day is unreadable: {error}")

    if not latest_date:
        _fail_validation(logger, "daily_summary has no usable day values")

    current_date = today_iso()
    days_old = _days_old(latest_date, current_date)
    is_stale = days_old > 1

    if days_old < 0:
        _fail_validation(
            logger,
            (
                f"latest recovery date {latest_date} is in the future; "
                f"current date is {current_date}"
            ),
        )

    if is_stale and not allow_stale:
        _fail_validation(
            logger,
            (
                f"latest recovery date {latest_date} is too stale; "
                f"current date is {current_date}"
            ),
        )

    result = {
        "status": "ready",
        "db_dir": str(db_dir),
        "validated_at": current_date,
        "latest_recovery_date": latest_date,
        "days_old": days_old,
        "is_stale": is_stale,
        "table_counts": table_counts,
    }
    logger.info("GarminDB validation passed: %s", result)
    return result


def parse_args():
    parser = argparse.ArgumentParser(description="Validate GarminDB health data.")
    parser.add_argument("--db-dir", default=str(DEFAULT_DB_DIR))
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument("--allow-stale", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        result = validate_garmindb(
            db_dir=args.db_dir,
            allow_stale=args.allow_stale,
            log_dir=args.log_dir,
        )
    except GarminDBImportError as error:
        print(f"GarminDB validation failed: {error}")
        return 1

    print(f"GarminDB validation passed: latest_recovery_date={result['latest_recovery_date']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
