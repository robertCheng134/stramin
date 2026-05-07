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


def _select_rows(connection, table_name, mapping):
    selected_columns = {
        details["column"]
        for details in mapping.values()
        if details.get("column") is not None
    }
    quoted_columns = ", ".join(f'"{column}"' for column in selected_columns)
    date_column = mapping["date"]["column"]
    query = f'SELECT {quoted_columns} FROM "{table_name}" ORDER BY "{date_column}"'
    cursor = connection.execute(query)
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


def load_health_data(db_path=None):
    path = resolve_garmindb_path(db_path)

    try:
        with sqlite3.connect(path) as connection:
            connection.row_factory = sqlite3.Row
            table_name = _find_supported_table(connection)
            columns = _list_columns(connection, table_name)
            mapping = _build_column_mapping(columns)
            rows = _select_rows(connection, table_name, mapping)
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


def load_health_rows(db_path=None):
    return [health_data.to_legacy_dict() for health_data in load_health_data(db_path)]
