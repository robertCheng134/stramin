import os
import sqlite3
from datetime import datetime
from pathlib import Path

from health_data import HealthData
from logger import get_logger


logger = get_logger(__name__)

SUPPORTED_TABLES = [
    "DailySummary",
    "daily_summary",
    "daily_health_metrics",
    "health_daily",
]

COLUMN_ALIASES = {
    "date": ["date", "day", "datetime", "calendar_date"],
    "sleep_hours": ["sleep_hours", "sleep_duration_hours", "total_sleep_hours"],
    "sleep_minutes": ["sleep_minutes", "sleep_duration_minutes", "total_sleep_minutes"],
    "hrv_status": ["hrv_status", "hrv_state", "hrv"],
    "hrv_value": ["heart_rate_variability", "hrv_ms", "hrv_avg"],
    "body_battery": [
        "body_battery",
        "body_battery_or_energy",
        "body_battery_avg",
        "body_battery_average",
        "bb_avg",
    ],
    "resting_hr": ["resting_hr", "resting_heart_rate", "rhr"],
    "stress": ["stress", "stress_avg", "average_stress", "stress_level"],
}

VALID_HRV_STATUSES = {"balanced", "low", "poor", "unbalanced"}


class GarminDBImportError(RuntimeError):
    pass


def resolve_garmindb_path(db_path=None):
    resolved_path = db_path or os.getenv("GARMINDB_PATH")
    if not resolved_path:
        raise GarminDBImportError(
            "Missing GarminDB path. Set GARMINDB_PATH or pass db_path."
        )

    path = Path(resolved_path).expanduser()
    if not path.exists():
        raise GarminDBImportError(f"GarminDB database file not found: {path}")

    if not path.is_file():
        raise GarminDBImportError(f"GarminDB path is not a file: {path}")

    return path


def _list_tables(connection):
    cursor = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    )
    return [row[0] for row in cursor.fetchall()]


def _find_supported_table(connection):
    tables = _list_tables(connection)
    table_lookup = {table.lower(): table for table in tables}

    for table in SUPPORTED_TABLES:
        if table.lower() in table_lookup:
            return table_lookup[table.lower()]

    raise GarminDBImportError(
        "GarminDB missing expected health summary table. Tried: "
        + ", ".join(SUPPORTED_TABLES)
    )


def _list_columns(connection, table_name):
    cursor = connection.execute(f'PRAGMA table_info("{table_name}")')
    return [row[1] for row in cursor.fetchall()]


def _has_table(connection, table_name):
    cursor = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND lower(name) = lower(?)",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _match_column(columns, aliases):
    column_lookup = {column.lower(): column for column in columns}
    for alias in aliases:
        if alias.lower() in column_lookup:
            return column_lookup[alias.lower()]
    return None


def _build_column_mapping(columns):
    date_column = _match_column(columns, COLUMN_ALIASES["date"])
    sleep_column = _match_column(columns, COLUMN_ALIASES["sleep_hours"])
    sleep_unit = "hours"
    if not sleep_column:
        sleep_column = _match_column(columns, COLUMN_ALIASES["sleep_minutes"])
        sleep_unit = "minutes"

    hrv_column = _match_column(columns, COLUMN_ALIASES["hrv_status"])
    hrv_kind = "status"
    if not hrv_column:
        hrv_column = _match_column(columns, COLUMN_ALIASES["hrv_value"])
        hrv_kind = "value"

    mapping = {
        "date": {"column": date_column},
        "sleep_hours": {"column": sleep_column, "unit": sleep_unit},
        "hrv_status": {"column": hrv_column, "kind": hrv_kind},
        "body_battery": {
            "column": _match_column(columns, COLUMN_ALIASES["body_battery"])
        },
        "resting_hr": {"column": _match_column(columns, COLUMN_ALIASES["resting_hr"])},
        "stress": {"column": _match_column(columns, COLUMN_ALIASES["stress"])},
    }

    missing_fields = [
        field
        for field in ["date", "sleep_hours", "hrv_status", "body_battery", "resting_hr"]
        if not mapping[field]["column"]
    ]
    if missing_fields:
        raise GarminDBImportError(
            "GarminDB table is missing required health columns: "
            + ", ".join(missing_fields)
        )

    return mapping


def _validate_start_date(value):
    date_text = str(value or "").strip()
    if not date_text:
        return None

    try:
        datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        logger.warning(
            "Invalid garmin_start_date '%s'. GarminDB import will not filter by start date.",
            value,
        )
        return None

    return date_text


def _resolve_garmin_start_date(user_profile=None):
    if user_profile is None:
        try:
            from user_profile import load_user_profile

            user_profile = load_user_profile()
        except Exception as error:
            logger.warning("Unable to load user profile for GarminDB import: %s", error)
            return None

    return _validate_start_date((user_profile or {}).get("garmin_start_date"))


def _select_rows(connection, table_name, mapping, start_date=None):
    selected_columns = {
        details["column"]
        for details in mapping.values()
        if details.get("column") is not None
    }
    quoted_columns = ", ".join(f'"{column}"' for column in selected_columns)
    date_column = mapping["date"]["column"]
    query = f'SELECT {quoted_columns} FROM "{table_name}"'
    params = ()
    if start_date:
        query += f' WHERE "{date_column}" >= ?'
        params = (start_date,)
    query += f' ORDER BY "{date_column}"'
    cursor = connection.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def _normalize_date(value):
    text = str(value or "").strip()
    if not text:
        raise ValueError("date is required")

    date_text = text.split("T")[0].split(" ")[0]
    datetime.strptime(date_text, "%Y-%m-%d")
    return date_text


def _normalize_sleep(value, unit):
    try:
        parsed_value = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("sleep_hours must be a number from 0 to 24") from error

    if unit == "minutes":
        parsed_value = parsed_value / 60

    if parsed_value < 0 or parsed_value > 24:
        raise ValueError("sleep_hours must be a number from 0 to 24")

    return str(round(parsed_value, 2))


def _normalize_int(value, min_value, max_value, label):
    try:
        parsed_value = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{label} must be an integer from {min_value} to {max_value}"
        ) from error

    if parsed_value < min_value or parsed_value > max_value:
        raise ValueError(f"{label} must be an integer from {min_value} to {max_value}")

    return str(parsed_value)


def _normalize_hrv_status(value, kind):
    if kind == "status":
        normalized_value = str(value or "").strip().lower()
        if normalized_value not in VALID_HRV_STATUSES:
            raise ValueError(
                "hrv_status must be one of balanced, low, poor, unbalanced"
            )
        return normalized_value

    try:
        hrv_value = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("hrv value must be numeric") from error

    if hrv_value >= 50:
        return "balanced"
    if hrv_value >= 35:
        return "unbalanced"
    if hrv_value >= 20:
        return "low"
    return "poor"


def _normalize_optional_int(value, min_value, max_value, label):
    if value in (None, ""):
        return ""
    return _normalize_int(value, min_value, max_value, label)


def _convert_row(row, mapping):
    date_value = _normalize_date(row.get(mapping["date"]["column"]))
    sleep_hours = _normalize_sleep(
        row.get(mapping["sleep_hours"]["column"]),
        mapping["sleep_hours"]["unit"],
    )
    hrv_status = _normalize_hrv_status(
        row.get(mapping["hrv_status"]["column"]),
        mapping["hrv_status"]["kind"],
    )
    body_battery = _normalize_int(
        row.get(mapping["body_battery"]["column"]),
        0,
        100,
        "body_battery",
    )
    resting_hr = _normalize_int(
        row.get(mapping["resting_hr"]["column"]),
        20,
        120,
        "resting_hr",
    )

    stress = ""
    stress_column = mapping["stress"]["column"]
    if stress_column and row.get(stress_column) not in (None, ""):
        stress = _normalize_int(row.get(stress_column), 0, 100, "stress")

    return HealthData(
        date=date_value,
        sleep_hours=sleep_hours,
        hrv_status=hrv_status,
        body_battery_or_energy=body_battery,
        resting_hr=resting_hr,
        stress=stress,
        source="garmindb",
    )


def _latest_date_from_monitoring(connection, start_date=None):
    date_queries = []
    params = ()
    if start_date:
        params = (start_date, start_date)
        date_filter = "WHERE date(timestamp) >= ?"
    else:
        date_filter = ""

    if _has_table(connection, "monitoring_hrv_status"):
        date_queries.append(
            f"SELECT date(timestamp) AS day FROM monitoring_hrv_status {date_filter}"
        )
    if _has_table(connection, "monitoring_hr"):
        date_queries.append(f"SELECT date(timestamp) AS day FROM monitoring_hr {date_filter}")

    if not date_queries:
        raise GarminDBImportError(
            "GarminDB monitoring database is missing monitoring_hrv_status and monitoring_hr tables."
        )

    query = "SELECT max(day) FROM (" + " UNION ALL ".join(date_queries) + ")"
    cursor = connection.execute(query, params[: len(date_queries)])
    latest_day = cursor.fetchone()[0]
    if not latest_day:
        raise GarminDBImportError("No GarminDB monitoring rows found.")

    return latest_day


def _fetch_one(connection, query, params=()):
    cursor = connection.execute(query, params)
    row = cursor.fetchone()
    return dict(row) if row else None


def _monitoring_hrv_to_status(row):
    if not row:
        return ""

    raw_status = row.get("status")
    if isinstance(raw_status, str) and raw_status.lower() in VALID_HRV_STATUSES:
        return raw_status.lower()

    last_night_average = row.get("last_night_average") or row.get("last_night")
    baseline_low = row.get("baseline_low")
    baseline_high = row.get("baseline_high")
    try:
        hrv_value = float(last_night_average)
        low = float(baseline_low)
        high = float(baseline_high)
    except (TypeError, ValueError):
        if last_night_average not in (None, ""):
            return _normalize_hrv_status(last_night_average, "value")
        return ""

    if hrv_value < low:
        return "low"
    if hrv_value > high:
        return "unbalanced"
    return "balanced"


def _load_latest_monitoring_health_data(connection, start_date=None):
    latest_day = _latest_date_from_monitoring(connection, start_date=start_date)

    hrv_row = None
    if _has_table(connection, "monitoring_hrv_status"):
        hrv_filter = ""
        hrv_params = ()
        if start_date:
            hrv_filter = "WHERE date(timestamp) >= ?"
            hrv_params = (start_date,)
        hrv_row = _fetch_one(
            connection,
            f"""
            SELECT timestamp, weekly_average, last_night, last_night_average,
                   baseline_low, baseline_high, status
            FROM monitoring_hrv_status
            {hrv_filter}
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            hrv_params,
        )

    hr_row = None
    if _has_table(connection, "monitoring_hr"):
        hr_row = _fetch_one(
            connection,
            """
            SELECT min(heart_rate) AS resting_hr
            FROM monitoring_hr
            WHERE date(timestamp) = ?
            """,
            (latest_day,),
        )

    hrv_status = _monitoring_hrv_to_status(hrv_row)
    resting_hr = _normalize_optional_int(
        (hr_row or {}).get("resting_hr"),
        20,
        120,
        "resting_hr",
    )

    if not hrv_status and not resting_hr:
        raise GarminDBImportError("No valid GarminDB monitoring health data found.")

    return HealthData(
        date=latest_day,
        sleep_hours="",
        hrv_status=hrv_status,
        body_battery_or_energy="",
        resting_hr=resting_hr,
        stress="",
        source="garmindb",
    )


def load_latest_health_data(db_path=None, user_profile=None):
    path = resolve_garmindb_path(db_path)
    start_date = _resolve_garmin_start_date(user_profile)

    try:
        with sqlite3.connect(path) as connection:
            connection.row_factory = sqlite3.Row
            try:
                table_name = _find_supported_table(connection)
            except GarminDBImportError:
                return _load_latest_monitoring_health_data(
                    connection,
                    start_date=start_date,
                )

            columns = _list_columns(connection, table_name)
            mapping = _build_column_mapping(columns)
            rows = _select_rows(connection, table_name, mapping, start_date=start_date)
    except sqlite3.Error as error:
        raise GarminDBImportError(f"Unable to read GarminDB database: {error}") from error

    if not rows:
        raise GarminDBImportError("No GarminDB health rows found.")

    for row in reversed(rows):
        try:
            return _convert_row(row, mapping)
        except ValueError as error:
            logger.warning("Skipping invalid GarminDB row: %s", error)

    raise GarminDBImportError("No valid GarminDB health data found.")


def load_health_data(db_path=None, user_profile=None):
    path = resolve_garmindb_path(db_path)
    start_date = _resolve_garmin_start_date(user_profile)

    try:
        with sqlite3.connect(path) as connection:
            connection.row_factory = sqlite3.Row
            table_name = _find_supported_table(connection)
            columns = _list_columns(connection, table_name)
            mapping = _build_column_mapping(columns)
            rows = _select_rows(connection, table_name, mapping, start_date=start_date)
    except sqlite3.Error as error:
        raise GarminDBImportError(f"Unable to read GarminDB database: {error}") from error

    if not rows:
        raise GarminDBImportError("No GarminDB health rows found.")

    health_data = []
    for row in rows:
        try:
            health_data.append(_convert_row(row, mapping))
        except ValueError as error:
            logger.warning("Skipping invalid GarminDB row: %s", error)

    if not health_data:
        raise GarminDBImportError("No valid GarminDB health data found.")

    return health_data


def load_health_rows(db_path=None, user_profile=None):
    return [
        health_data.to_legacy_dict()
        for health_data in load_health_data(db_path, user_profile=user_profile)
    ]
