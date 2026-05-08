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


def _metric_metadata(
    value="",
    date="",
    db_file="",
    table="",
    column="",
    timestamp="",
    raw_value="",
    reason="",
):
    return {
        "value": value,
        "date": date,
        "db_file": str(db_file) if db_file else "",
        "table": table,
        "column": column,
        "timestamp": timestamp,
        "raw_value": raw_value,
        "reason": reason,
    }


def _date_from_timestamp(value):
    if value in (None, ""):
        return ""
    return str(value).split("T")[0].split(" ")[0]


def _time_to_hours(value):
    text = str(value or "").strip()
    if not text:
        return ""

    parts = text.split(":")
    if len(parts) < 2:
        return ""

    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return ""

    return str(round(hours + (minutes / 60) + (seconds / 3600), 2))


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


def _load_latest_monitoring_health_data_with_metadata(
    connection,
    tables,
    start_date=None,
    db_file="",
):
    latest_day = _latest_date_from_monitoring(connection, start_date=start_date)
    metrics = {
        "sleep_hours": _metric_metadata(reason="table not found"),
        "hrv_status": _metric_metadata(reason="table not found"),
        "resting_hr": _metric_metadata(reason="table not found"),
        "body_battery": _metric_metadata(reason="table not found"),
        "stress": _metric_metadata(reason="table not found"),
    }

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
        if hrv_row:
            raw_column = "last_night_average"
            raw_value = hrv_row.get(raw_column)
            if raw_value in (None, ""):
                raw_column = "last_night"
                raw_value = hrv_row.get(raw_column)
            if raw_value in (None, ""):
                raw_column = "status"
                raw_value = hrv_row.get(raw_column)

            hrv_status = _monitoring_hrv_to_status(hrv_row)
            metrics["hrv_status"] = _metric_metadata(
                value=hrv_status,
                date=_date_from_timestamp(hrv_row.get("timestamp")),
                db_file=db_file,
                table="monitoring_hrv_status",
                column=raw_column,
                timestamp=hrv_row.get("timestamp") or "",
                raw_value=raw_value if raw_value is not None else "",
                reason="" if hrv_status else "no recent rows",
            )
        else:
            metrics["hrv_status"] = _metric_metadata(
                db_file=db_file,
                table="monitoring_hrv_status",
                reason="no recent rows",
            )

    hr_row = None
    if _has_table(connection, "monitoring_hr"):
        hr_row = _fetch_one(
            connection,
            """
            SELECT timestamp, heart_rate AS resting_hr
            FROM monitoring_hr
            WHERE date(timestamp) = ?
            ORDER BY heart_rate ASC, timestamp DESC
            LIMIT 1
            """,
            (latest_day,),
        )
        if hr_row:
            try:
                resting_hr = _normalize_optional_int(
                    hr_row.get("resting_hr"),
                    20,
                    120,
                    "resting_hr",
                )
            except ValueError:
                resting_hr = ""
            metrics["resting_hr"] = _metric_metadata(
                value=resting_hr,
                date=_date_from_timestamp(hr_row.get("timestamp")),
                db_file=db_file,
                table="monitoring_hr",
                column="heart_rate",
                timestamp=hr_row.get("timestamp") or "",
                raw_value=hr_row.get("resting_hr") or "",
                reason="" if resting_hr else "no recent rows",
            )
        else:
            metrics["resting_hr"] = _metric_metadata(
                db_file=db_file,
                table="monitoring_hr",
                column="heart_rate",
                reason="no recent rows",
            )

    hrv_status = metrics["hrv_status"]["value"]
    resting_hr = metrics["resting_hr"]["value"]

    if not hrv_status and not resting_hr:
        raise GarminDBImportError("No valid GarminDB monitoring health data found.")

    health_data = HealthData(
        date=latest_day,
        sleep_hours=metrics["sleep_hours"]["value"],
        hrv_status=hrv_status,
        body_battery_or_energy=metrics["body_battery"]["value"],
        resting_hr=resting_hr,
        stress=metrics["stress"]["value"],
        source="garmindb",
    )

    return health_data, {
        "schema": "monitoring",
        "db_file": str(db_file) if db_file else "",
        "tables": tables,
        "source_date": latest_day,
        "metrics": metrics,
    }


def _load_latest_monitoring_health_data(connection, start_date=None):
    health_data, _metadata = _load_latest_monitoring_health_data_with_metadata(
        connection,
        _list_tables(connection),
        start_date=start_date,
    )
    return health_data


def resolve_garmindb_dir(db_dir=None):
    resolved_dir = db_dir or os.getenv("GARMINDB_DIR") or "~/HealthData/DBs"
    path = Path(resolved_dir).expanduser()
    if not path.exists():
        raise GarminDBImportError(f"GarminDB directory not found: {path}")
    if not path.is_dir():
        raise GarminDBImportError(f"GarminDB path is not a directory: {path}")
    return path


def _empty_metrics():
    return {
        "sleep_hours": _metric_metadata(reason="unsupported GarminDB schema"),
        "hrv_status": _metric_metadata(reason="unsupported GarminDB schema"),
        "resting_hr": _metric_metadata(reason="unsupported GarminDB schema"),
        "body_battery": _metric_metadata(reason="table not found"),
        "stress": _metric_metadata(reason="unsupported GarminDB schema"),
    }


def _metric_table_not_found(db_file, table, column=""):
    return _metric_metadata(
        db_file=db_file,
        table=table,
        column=column,
        reason="table not found",
    )


def _metric_column_not_found(db_file, table, column=""):
    return _metric_metadata(
        db_file=db_file,
        table=table,
        column=column,
        reason="column not found",
    )


def _metric_no_recent_rows(db_file, table, column):
    return _metric_metadata(
        db_file=db_file,
        table=table,
        column=column,
        reason="no recent rows",
    )


def _latest_sleep_metric(connection, db_file, start_date=None):
    if not _has_table(connection, "sleep"):
        return _metric_table_not_found(db_file, "sleep", "total_sleep")

    columns = _list_columns(connection, "sleep")
    if "day" not in columns:
        return _metric_column_not_found(db_file, "sleep", "day")
    if "total_sleep" not in columns:
        return _metric_column_not_found(db_file, "sleep", "total_sleep")

    query = 'SELECT day, total_sleep FROM sleep'
    params = ()
    if start_date:
        query += ' WHERE date(day) >= ?'
        params = (start_date,)
    query += ' ORDER BY day DESC LIMIT 1'
    row = _fetch_one(connection, query, params)
    if not row:
        return _metric_no_recent_rows(db_file, "sleep", "total_sleep")

    sleep_hours = _time_to_hours(row.get("total_sleep"))
    return _metric_metadata(
        value=sleep_hours,
        date=_date_from_timestamp(row.get("day")),
        db_file=db_file,
        table="sleep",
        column="total_sleep",
        timestamp=row.get("day") or "",
        raw_value=row.get("total_sleep") or "",
        reason="" if sleep_hours else "no recent rows",
    )


def _latest_stress_metric(connection, db_file, start_date=None):
    if not _has_table(connection, "stress"):
        return _metric_table_not_found(db_file, "stress", "stress")

    columns = _list_columns(connection, "stress")
    if "timestamp" not in columns:
        return _metric_column_not_found(db_file, "stress", "timestamp")
    if "stress" not in columns:
        return _metric_column_not_found(db_file, "stress", "stress")

    query = 'SELECT timestamp, stress FROM stress'
    params = ()
    if start_date:
        query += ' WHERE date(timestamp) >= ?'
        params = (start_date,)
    query += ' ORDER BY timestamp DESC LIMIT 1'
    row = _fetch_one(connection, query, params)
    if not row:
        return _metric_no_recent_rows(db_file, "stress", "stress")

    try:
        stress = _normalize_optional_int(row.get("stress"), 0, 100, "stress")
    except ValueError:
        stress = ""
    return _metric_metadata(
        value=stress,
        date=_date_from_timestamp(row.get("timestamp")),
        db_file=db_file,
        table="stress",
        column="stress",
        timestamp=row.get("timestamp") or "",
        raw_value=row.get("stress") or "",
        reason="" if stress else "no recent rows",
    )


def _latest_resting_hr_metric_from_garmin(connection, db_file, start_date=None):
    if not _has_table(connection, "resting_hr"):
        return _metric_table_not_found(db_file, "resting_hr", "resting_heart_rate")

    columns = _list_columns(connection, "resting_hr")
    if "day" not in columns:
        return _metric_column_not_found(db_file, "resting_hr", "day")
    if "resting_heart_rate" not in columns:
        return _metric_column_not_found(db_file, "resting_hr", "resting_heart_rate")

    query = 'SELECT day, resting_heart_rate FROM resting_hr'
    params = ()
    if start_date:
        query += ' WHERE date(day) >= ?'
        params = (start_date,)
    query += ' ORDER BY day DESC LIMIT 1'
    row = _fetch_one(connection, query, params)
    if not row:
        return _metric_no_recent_rows(db_file, "resting_hr", "resting_heart_rate")

    try:
        resting_hr = _normalize_optional_int(
            row.get("resting_heart_rate"),
            20,
            120,
            "resting_hr",
        )
    except ValueError:
        resting_hr = ""
    return _metric_metadata(
        value=resting_hr,
        date=_date_from_timestamp(row.get("day")),
        db_file=db_file,
        table="resting_hr",
        column="resting_heart_rate",
        timestamp=row.get("day") or "",
        raw_value=row.get("resting_heart_rate") or "",
        reason="" if resting_hr else "no recent rows",
    )


def _latest_hrv_metric_from_garmin(connection, db_file, start_date=None):
    if not _has_table(connection, "hrv"):
        return _metric_table_not_found(db_file, "hrv", "status")

    columns = _list_columns(connection, "hrv")
    if "day" not in columns:
        return _metric_column_not_found(db_file, "hrv", "day")

    status_column = "status" if "status" in columns else None
    value_column = "last_night_avg" if "last_night_avg" in columns else None
    if not status_column and not value_column:
        return _metric_column_not_found(db_file, "hrv", "status")

    selected_columns = ["day"]
    if status_column:
        selected_columns.append(status_column)
    if value_column:
        selected_columns.append(value_column)
    query = "SELECT " + ", ".join(selected_columns) + " FROM hrv"
    params = ()
    if start_date:
        query += " WHERE date(day) >= ?"
        params = (start_date,)
    query += " ORDER BY day DESC LIMIT 1"
    row = _fetch_one(connection, query, params)
    if not row:
        return _metric_no_recent_rows(db_file, "hrv", status_column or value_column)

    raw_column = status_column or value_column
    raw_value = row.get(raw_column)
    hrv_status = ""
    if status_column and str(row.get(status_column) or "").lower() in VALID_HRV_STATUSES:
        hrv_status = str(row.get(status_column)).lower()
    elif value_column and row.get(value_column) not in (None, ""):
        hrv_status = _normalize_hrv_status(row.get(value_column), "value")
        raw_column = value_column
        raw_value = row.get(value_column)

    return _metric_metadata(
        value=hrv_status,
        date=_date_from_timestamp(row.get("day")),
        db_file=db_file,
        table="hrv",
        column=raw_column,
        timestamp=row.get("day") or "",
        raw_value=raw_value if raw_value is not None else "",
        reason="" if hrv_status else "no recent rows",
    )


def _read_monitoring_metrics(monitoring_path, start_date=None):
    metrics = {
        "hrv_status": _metric_table_not_found(
            monitoring_path,
            "monitoring_hrv_status",
            "last_night_average",
        ),
        "resting_hr": _metric_table_not_found(
            monitoring_path,
            "monitoring_hr",
            "heart_rate",
        ),
    }
    tables = []
    if not monitoring_path.exists():
        return metrics, tables

    with sqlite3.connect(monitoring_path) as connection:
        connection.row_factory = sqlite3.Row
        tables = _list_tables(connection)
        try:
            _health_data, metadata = _load_latest_monitoring_health_data_with_metadata(
                connection,
                tables,
                start_date=start_date,
                db_file=monitoring_path,
            )
        except GarminDBImportError:
            return metrics, tables

    metrics["hrv_status"] = metadata["metrics"]["hrv_status"]
    metrics["resting_hr"] = metadata["metrics"]["resting_hr"]
    return metrics, tables


def _read_garmin_metrics(garmin_path, start_date=None):
    metrics = {
        "sleep_hours": _metric_table_not_found(garmin_path, "sleep", "total_sleep"),
        "stress": _metric_table_not_found(garmin_path, "stress", "stress"),
        "resting_hr": _metric_table_not_found(
            garmin_path,
            "resting_hr",
            "resting_heart_rate",
        ),
        "hrv_status": _metric_table_not_found(garmin_path, "hrv", "status"),
    }
    tables = []
    if not garmin_path.exists():
        return metrics, tables

    with sqlite3.connect(garmin_path) as connection:
        connection.row_factory = sqlite3.Row
        tables = _list_tables(connection)
        metrics["sleep_hours"] = _latest_sleep_metric(
            connection,
            garmin_path,
            start_date=start_date,
        )
        metrics["stress"] = _latest_stress_metric(
            connection,
            garmin_path,
            start_date=start_date,
        )
        metrics["resting_hr"] = _latest_resting_hr_metric_from_garmin(
            connection,
            garmin_path,
            start_date=start_date,
        )
        metrics["hrv_status"] = _latest_hrv_metric_from_garmin(
            connection,
            garmin_path,
            start_date=start_date,
        )

    return metrics, tables


def _source_date_from_metrics(metrics):
    dates = [
        metric.get("date")
        for metric in metrics.values()
        if metric.get("value") and metric.get("date")
    ]
    return max(dates) if dates else ""


def load_latest_health_data_from_directory(db_dir=None, user_profile=None):
    directory = resolve_garmindb_dir(db_dir)
    start_date = _resolve_garmin_start_date(user_profile)
    monitoring_path = directory / "garmin_monitoring.db"
    garmin_path = directory / "garmin.db"

    monitoring_metrics, monitoring_tables = _read_monitoring_metrics(
        monitoring_path,
        start_date=start_date,
    )
    garmin_metrics, garmin_tables = _read_garmin_metrics(
        garmin_path,
        start_date=start_date,
    )

    metrics = _empty_metrics()
    metrics["hrv_status"] = monitoring_metrics["hrv_status"]
    if not metrics["hrv_status"].get("value") and garmin_metrics["hrv_status"].get(
        "value"
    ):
        metrics["hrv_status"] = garmin_metrics["hrv_status"]

    metrics["resting_hr"] = monitoring_metrics["resting_hr"]
    if not metrics["resting_hr"].get("value") and garmin_metrics["resting_hr"].get(
        "value"
    ):
        metrics["resting_hr"] = garmin_metrics["resting_hr"]

    metrics["sleep_hours"] = garmin_metrics["sleep_hours"]
    metrics["stress"] = garmin_metrics["stress"]
    metrics["body_battery"] = _metric_table_not_found(
        garmin_path,
        "body_battery",
        "body_battery",
    )

    source_date = _source_date_from_metrics(metrics)
    if not source_date:
        raise GarminDBImportError("No valid GarminDB health data found.")

    health_data = HealthData(
        date=source_date,
        sleep_hours=metrics["sleep_hours"]["value"],
        hrv_status=metrics["hrv_status"]["value"],
        body_battery_or_energy=metrics["body_battery"]["value"],
        resting_hr=metrics["resting_hr"]["value"],
        stress=metrics["stress"]["value"],
        source="garmindb",
    )

    return health_data, {
        "schema": "directory",
        "db_dir": str(directory),
        "db_files": {
            "garmin_monitoring.db": str(monitoring_path),
            "garmin.db": str(garmin_path),
        },
        "tables_by_db": {
            "garmin_monitoring.db": monitoring_tables,
            "garmin.db": garmin_tables,
        },
        "source_date": source_date,
        "metrics": metrics,
    }


def _daily_summary_metadata(row, mapping, table_name, tables, health_data, db_file=""):
    date_column = mapping["date"]["column"]
    source_date = health_data.date
    metrics = {
        "sleep_hours": _metric_metadata(
            value=health_data.sleep_hours,
            date=source_date,
            db_file=db_file,
            table=table_name,
            column=mapping["sleep_hours"]["column"],
            timestamp=row.get(date_column) or "",
            raw_value=row.get(mapping["sleep_hours"]["column"]) or "",
        ),
        "hrv_status": _metric_metadata(
            value=health_data.hrv_status,
            date=source_date,
            db_file=db_file,
            table=table_name,
            column=mapping["hrv_status"]["column"],
            timestamp=row.get(date_column) or "",
            raw_value=row.get(mapping["hrv_status"]["column"]) or "",
        ),
        "resting_hr": _metric_metadata(
            value=health_data.resting_hr,
            date=source_date,
            db_file=db_file,
            table=table_name,
            column=mapping["resting_hr"]["column"],
            timestamp=row.get(date_column) or "",
            raw_value=row.get(mapping["resting_hr"]["column"]) or "",
        ),
        "body_battery": _metric_metadata(
            value=health_data.body_battery_or_energy,
            date=source_date,
            db_file=db_file,
            table=table_name,
            column=mapping["body_battery"]["column"],
            timestamp=row.get(date_column) or "",
            raw_value=row.get(mapping["body_battery"]["column"]) or "",
        ),
    }

    stress_column = mapping["stress"]["column"]
    if stress_column:
        metrics["stress"] = _metric_metadata(
            value=health_data.stress,
            date=source_date if health_data.stress else "",
            db_file=db_file,
            table=table_name,
            column=stress_column,
            timestamp=row.get(date_column) or "",
            raw_value=row.get(stress_column) or "",
            reason="" if health_data.stress else "no recent rows",
        )
    else:
        metrics["stress"] = _metric_metadata(
            db_file=db_file,
            table=table_name,
            reason="column not found",
        )

    return {
        "schema": "daily_summary",
        "db_file": str(db_file) if db_file else "",
        "tables": tables,
        "source_date": source_date,
        "metrics": metrics,
    }


def load_latest_health_data_with_metadata(db_path=None, db_dir=None, user_profile=None):
    if db_dir is not None:
        return load_latest_health_data_from_directory(
            db_dir=db_dir,
            user_profile=user_profile,
        )

    path = resolve_garmindb_path(db_path)
    start_date = _resolve_garmin_start_date(user_profile)

    try:
        with sqlite3.connect(path) as connection:
            connection.row_factory = sqlite3.Row
            tables = _list_tables(connection)
            try:
                table_name = _find_supported_table(connection)
            except GarminDBImportError:
                return _load_latest_monitoring_health_data_with_metadata(
                    connection,
                tables,
                start_date=start_date,
                db_file=path,
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
            health_data = _convert_row(row, mapping)
            metadata = _daily_summary_metadata(
                row,
                mapping,
                table_name,
                tables,
                health_data,
                db_file=path,
            )
            return health_data, metadata
        except ValueError as error:
            logger.warning("Skipping invalid GarminDB row: %s", error)

    raise GarminDBImportError("No valid GarminDB health data found.")


def load_latest_health_data(db_path=None, db_dir=None, user_profile=None):
    health_data, _metadata = load_latest_health_data_with_metadata(
        db_path,
        db_dir=db_dir,
        user_profile=user_profile,
    )
    return health_data



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
