import sqlite3
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from integrations.garmindb import (
    GarminDBImportError,
    load_health_data,
    load_latest_health_data,
    load_latest_health_data_with_metadata,
)


def _create_daily_summary_db(path, rows):
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE DailySummary (
                day TEXT,
                sleep_minutes INTEGER,
                hrv_status TEXT,
                body_battery INTEGER,
                resting_heart_rate INTEGER,
                stress INTEGER
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO DailySummary (
                day,
                sleep_minutes,
                hrv_status,
                body_battery,
                resting_heart_rate,
                stress
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def test_garmindb_adapter_returns_unified_health_data(tmp_path):
    db_path = tmp_path / "garmin.db"
    _create_daily_summary_db(
        db_path,
        [("2026-05-07", 450, "balanced", 72, 55, 25)],
    )

    health_data = load_health_data(db_path)[0]

    assert health_data.date == "2026-05-07"
    assert health_data.sleep_hours == "7.5"
    assert health_data.hrv_status == "balanced"
    assert health_data.body_battery_or_energy == "72"
    assert health_data.resting_hr == "55"
    assert health_data.stress == "25"
    assert health_data.source == "garmindb"


def test_garmindb_latest_health_data_returns_latest_daily_summary(tmp_path):
    db_path = tmp_path / "garmin.db"
    _create_daily_summary_db(
        db_path,
        [
            ("2026-05-06", 450, "balanced", 72, 55, 25),
            ("2026-05-07", 420, "low", 60, 58, 35),
        ],
    )

    health_data = load_latest_health_data(db_path)

    assert health_data.date == "2026-05-07"
    assert health_data.hrv_status == "low"
    assert health_data.resting_hr == "58"


def test_garmindb_latest_health_data_metadata_for_daily_summary(tmp_path):
    db_path = tmp_path / "garmin.db"
    _create_daily_summary_db(
        db_path,
        [("2026-05-07", 420, "low", 60, 58, None)],
    )

    health_data, metadata = load_latest_health_data_with_metadata(db_path)

    assert health_data.date == "2026-05-07"
    assert metadata["source_date"] == "2026-05-07"
    assert metadata["metrics"]["sleep_hours"]["date"] == "2026-05-07"
    assert metadata["metrics"]["sleep_hours"]["table"] == "DailySummary"
    assert metadata["metrics"]["sleep_hours"]["column"] == "sleep_minutes"
    assert metadata["metrics"]["sleep_hours"]["raw_value"] == 420
    assert metadata["metrics"]["stress"]["reason"] == "no recent rows"


def test_garmindb_adapter_uses_env_path(tmp_path, monkeypatch):
    db_path = tmp_path / "garmin.db"
    _create_daily_summary_db(
        db_path,
        [("2026-05-07", 420, "low", 48, 60, None)],
    )
    monkeypatch.setenv("GARMINDB_PATH", str(db_path))

    health_data = load_health_data()[0]

    assert health_data.date == "2026-05-07"
    assert health_data.sleep_hours == "7.0"
    assert health_data.stress == ""


def test_garmindb_adapter_maps_numeric_hrv_value(tmp_path):
    db_path = tmp_path / "garmin.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE daily_health_metrics (
                date TEXT,
                sleep_hours REAL,
                heart_rate_variability REAL,
                body_battery_avg INTEGER,
                resting_hr INTEGER
            )
            """
        )
        connection.execute(
            """
            INSERT INTO daily_health_metrics (
                date,
                sleep_hours,
                heart_rate_variability,
                body_battery_avg,
                resting_hr
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            ("2026-05-07", 8.0, 28.0, 80, 53),
        )

    health_data = load_health_data(db_path)[0]

    assert health_data.hrv_status == "low"


def test_garmindb_adapter_requires_path(monkeypatch):
    monkeypatch.delenv("GARMINDB_PATH", raising=False)

    with pytest.raises(GarminDBImportError, match="Missing GarminDB path"):
        load_health_data()


def test_garmindb_adapter_rejects_missing_file(tmp_path):
    with pytest.raises(GarminDBImportError, match="database file not found"):
        load_health_data(tmp_path / "missing.db")


def test_garmindb_adapter_rejects_missing_expected_table(tmp_path):
    db_path = tmp_path / "garmin.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE OtherTable (date TEXT)")

    with pytest.raises(GarminDBImportError, match="missing expected health summary table"):
        load_health_data(db_path)


def test_garmindb_adapter_rejects_empty_result(tmp_path):
    db_path = tmp_path / "garmin.db"
    _create_daily_summary_db(db_path, [])

    with pytest.raises(GarminDBImportError, match="No GarminDB health rows found"):
        load_health_data(db_path)


def test_garmindb_adapter_skips_invalid_rows(tmp_path):
    db_path = tmp_path / "garmin.db"
    _create_daily_summary_db(
        db_path,
        [
            ("bad-date", 450, "balanced", 72, 55, 25),
            ("2026-05-07", 420, "unbalanced", 62, 58, 30),
        ],
    )

    health_data = load_health_data(db_path)

    assert len(health_data) == 1
    assert health_data[0].date == "2026-05-07"


def test_garmindb_adapter_filters_before_garmin_start_date(tmp_path):
    db_path = tmp_path / "garmin.db"
    _create_daily_summary_db(
        db_path,
        [
            ("2026-04-30", 450, "balanced", 72, 55, 25),
            ("2026-05-07", 420, "balanced", 62, 58, 30),
        ],
    )

    health_data = load_health_data(
        db_path,
        user_profile={"garmin_start_date": "2026-05-01"},
    )

    assert [row.date for row in health_data] == ["2026-05-07"]


def test_garmindb_adapter_ignores_invalid_garmin_start_date(tmp_path):
    db_path = tmp_path / "garmin.db"
    _create_daily_summary_db(
        db_path,
        [
            ("2026-04-30", 450, "balanced", 72, 55, 25),
            ("2026-05-07", 420, "balanced", 62, 58, 30),
        ],
    )

    health_data = load_health_data(
        db_path,
        user_profile={"garmin_start_date": "not-a-date"},
    )

    assert [row.date for row in health_data] == ["2026-04-30", "2026-05-07"]


def test_garmindb_latest_health_data_reads_monitoring_schema(tmp_path):
    db_path = tmp_path / "garmin_monitoring.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE monitoring_hrv_status (
                timestamp DATETIME NOT NULL,
                weekly_average FLOAT,
                last_night FLOAT,
                last_night_average FLOAT,
                baseline_low FLOAT,
                baseline_high FLOAT,
                status INTEGER,
                reading_count INTEGER,
                PRIMARY KEY (timestamp)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE monitoring_hr (
                timestamp DATETIME NOT NULL,
                heart_rate INTEGER NOT NULL,
                PRIMARY KEY (timestamp)
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO monitoring_hrv_status (
                timestamp,
                weekly_average,
                last_night,
                last_night_average,
                baseline_low,
                baseline_high,
                status,
                reading_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("2026-05-06 23:00:00", 34, 32, 34, 35, 39, 2, 10),
                ("2026-05-07 23:00:00", 36, 37, 37, 35, 39, 3, 10),
            ],
        )
        connection.executemany(
            "INSERT INTO monitoring_hr (timestamp, heart_rate) VALUES (?, ?)",
            [
                ("2026-05-07 01:00:00", 70),
                ("2026-05-07 02:00:00", 52),
                ("2026-05-07 03:00:00", 55),
            ],
        )

    health_data = load_latest_health_data(db_path)

    assert health_data.date == "2026-05-07"
    assert health_data.sleep_hours == ""
    assert health_data.hrv_status == "balanced"
    assert health_data.resting_hr == "52"
    assert health_data.body_battery_or_energy == ""

    _health_data, metadata = load_latest_health_data_with_metadata(db_path)
    assert metadata["source_date"] == "2026-05-07"
    assert metadata["metrics"]["hrv_status"]["date"] == "2026-05-07"
    assert metadata["metrics"]["hrv_status"]["table"] == "monitoring_hrv_status"
    assert metadata["metrics"]["hrv_status"]["column"] == "last_night"
    assert metadata["metrics"]["hrv_status"]["semantic_source"] == "nightly_hrv_average"
    assert metadata["metrics"]["hrv_status"]["source_priority"] == "fallback"
    assert metadata["metrics"]["hrv_status"]["hrv_value"] == "37.0"
    assert metadata["metrics"]["hrv_status"]["hrv_value_semantic_source"] == "nightly_hrv_average"
    assert metadata["metrics"]["hrv_status"]["hrv_5min_high"] == "37.0"
    assert metadata["metrics"]["hrv_status"]["hrv_5min_high_semantic_source"] == "nightly_hrv_5min_high"
    assert metadata["metrics"]["hrv_status"]["hrv_unit"] == "ms"
    assert metadata["metrics"]["hrv_status"]["garmin_hrv_status"] == "3"
    assert metadata["metrics"]["hrv_status"]["hrv_lower_bound"] == "35.0"
    assert metadata["metrics"]["hrv_status"]["hrv_upper_bound"] == "39.0"
    assert metadata["metrics"]["hrv_status"]["hrv_balance"] == "within_baseline"
    assert metadata["metrics"]["hrv_status"]["hrv_risk"] == "stable"
    assert (
        metadata["metrics"]["hrv_status"]["hrv_message"]
        == "HRV is within your normal baseline range."
    )
    assert metadata["metrics"]["resting_hr"]["date"] == "2026-05-07"
    assert metadata["metrics"]["resting_hr"]["column"] == "heart_rate"
    assert (
        metadata["metrics"]["resting_hr"]["semantic_source"]
        == "monitoring_heart_rate"
    )
    assert metadata["metrics"]["resting_hr"]["source_priority"] == "fallback"
    assert metadata["metrics"]["sleep_hours"]["reason"] == "table not found"
    assert metadata["metrics"]["body_battery"]["reason"] == "table not found"


def test_garmindb_latest_health_data_uses_latest_available_hrv(tmp_path):
    db_path = tmp_path / "garmin_monitoring.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE monitoring_hrv_status (
                timestamp DATETIME NOT NULL,
                weekly_average FLOAT,
                last_night FLOAT,
                last_night_average FLOAT,
                baseline_low FLOAT,
                baseline_high FLOAT,
                status INTEGER,
                reading_count INTEGER,
                PRIMARY KEY (timestamp)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE monitoring_hr (
                timestamp DATETIME NOT NULL,
                heart_rate INTEGER NOT NULL,
                PRIMARY KEY (timestamp)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO monitoring_hrv_status (
                timestamp,
                weekly_average,
                last_night,
                last_night_average,
                baseline_low,
                baseline_high,
                status,
                reading_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("2026-05-06 23:00:00", 34, 32, 32, 35, 39, 2, 10),
        )
        connection.execute(
            "INSERT INTO monitoring_hr (timestamp, heart_rate) VALUES (?, ?)",
            ("2026-05-07 02:00:00", 58),
        )

    health_data = load_latest_health_data(db_path)

    assert health_data.date == "2026-05-07"
    assert health_data.hrv_status == "low"
    assert health_data.resting_hr == "58"


def _create_garmin_db(path):
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE sleep (
                day DATETIME NOT NULL PRIMARY KEY,
                total_sleep TIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE stress (
                timestamp DATETIME NOT NULL PRIMARY KEY,
                stress INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE resting_hr (
                day DATETIME NOT NULL PRIMARY KEY,
                resting_heart_rate FLOAT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE hrv (
                day DATETIME NOT NULL PRIMARY KEY,
                last_night_avg INTEGER,
                last_night_5min_high INTEGER,
                baseline_low INTEGER,
                baseline_upper INTEGER,
                status VARCHAR
            )
            """
        )
        connection.execute(
            "INSERT INTO sleep (day, total_sleep) VALUES (?, ?)",
            ("2026-05-07 00:00:00", "07:30:00.000000"),
        )
        connection.execute(
            "INSERT INTO stress (timestamp, stress) VALUES (?, ?)",
            ("2026-05-07 16:00:00", 42),
        )
        connection.execute(
            "INSERT INTO resting_hr (day, resting_heart_rate) VALUES (?, ?)",
            ("2026-05-07 00:00:00", 62.0),
        )
        connection.execute(
            """
            INSERT INTO hrv (
                day,
                last_night_avg,
                last_night_5min_high,
                baseline_low,
                baseline_upper,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("2026-05-07 00:00:00", 31, 55, 35, 39, "low"),
        )


def _create_monitoring_db(path, include_hr=True):
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE monitoring_hrv_status (
                timestamp DATETIME NOT NULL,
                weekly_average FLOAT,
                last_night FLOAT,
                last_night_average FLOAT,
                baseline_low FLOAT,
                baseline_high FLOAT,
                status INTEGER,
                reading_count INTEGER,
                PRIMARY KEY (timestamp)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO monitoring_hrv_status (
                timestamp,
                weekly_average,
                last_night,
                last_night_average,
                baseline_low,
                baseline_high,
                status,
                reading_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("2026-05-06 23:00:00", 34, 48, 48, 35, 39, 2, 10),
        )
        if include_hr:
            connection.execute(
                """
                CREATE TABLE monitoring_hr (
                    timestamp DATETIME NOT NULL,
                    heart_rate INTEGER NOT NULL,
                    PRIMARY KEY (timestamp)
                )
                """
            )
            connection.executemany(
                "INSERT INTO monitoring_hr (timestamp, heart_rate) VALUES (?, ?)",
                [
                    ("2026-05-07 01:00:00", 70),
                    ("2026-05-07 02:00:00", 54),
                ],
            )


def test_garmindb_latest_directory_combines_monitoring_and_garmin_db(tmp_path):
    db_dir = tmp_path / "DBs"
    db_dir.mkdir()
    _create_monitoring_db(db_dir / "garmin_monitoring.db")
    _create_garmin_db(db_dir / "garmin.db")

    health_data, metadata = load_latest_health_data_with_metadata(db_dir=db_dir)

    assert health_data.date == "2026-05-07"
    assert health_data.sleep_hours == "7.5"
    assert health_data.hrv_status == "low"
    assert health_data.resting_hr == "62"
    assert health_data.stress == "42"
    assert metadata["schema"] == "directory"
    assert metadata["metrics"]["sleep_hours"]["db_file"].endswith("garmin.db")
    assert metadata["metrics"]["sleep_hours"]["semantic_source"] == "sleep_summary"
    assert metadata["metrics"]["sleep_hours"]["source_priority"] == "primary"
    assert metadata["metrics"]["hrv_status"]["db_file"].endswith("garmin.db")
    assert metadata["metrics"]["hrv_status"]["semantic_source"] == "nightly_hrv_average"
    assert metadata["metrics"]["hrv_status"]["source_priority"] == "primary"
    assert metadata["metrics"]["resting_hr"]["table"] == "resting_hr"
    assert (
        metadata["metrics"]["resting_hr"]["semantic_source"] == "official_resting_hr"
    )
    assert metadata["metrics"]["resting_hr"]["source_priority"] == "primary"
    assert metadata["metrics"]["body_battery"]["reason"] == "table not found"
    assert metadata["metrics"]["hrv_status"]["hrv_value"] == "31"
    assert metadata["metrics"]["hrv_status"]["hrv_5min_high"] == "55"
    assert metadata["metrics"]["hrv_status"]["hrv_balance"] == "below_baseline"
    assert (
        metadata["metrics"]["hrv_status"]["hrv_risk"]
        == "possible_under_recovery"
    )
    assert "below your baseline" in metadata["metrics"]["hrv_status"]["hrv_message"]
    assert metadata["metrics"]["stress"]["raw_value"] == 42
    assert metadata["metrics"]["stress"]["selected_value"] == "42"
    assert metadata["metrics"]["stress"]["invalid_rows_skipped"] == 0


def test_garmindb_latest_directory_falls_back_to_garmin_resting_hr(tmp_path):
    db_dir = tmp_path / "DBs"
    db_dir.mkdir()
    _create_monitoring_db(db_dir / "garmin_monitoring.db", include_hr=False)
    _create_garmin_db(db_dir / "garmin.db")

    health_data, metadata = load_latest_health_data_with_metadata(db_dir=db_dir)

    assert health_data.resting_hr == "62"
    assert metadata["metrics"]["resting_hr"]["table"] == "resting_hr"


def test_garmindb_stress_skips_latest_negative_value(tmp_path):
    db_dir = tmp_path / "DBs"
    db_dir.mkdir()
    _create_garmin_db(db_dir / "garmin.db")
    with sqlite3.connect(db_dir / "garmin.db") as connection:
        connection.execute(
            "INSERT INTO stress (timestamp, stress) VALUES (?, ?)",
            ("2026-05-08 16:00:00", -2),
        )

    health_data, metadata = load_latest_health_data_with_metadata(db_dir=db_dir)

    assert health_data.stress == "42"
    assert metadata["metrics"]["stress"]["raw_value"] == -2
    assert metadata["metrics"]["stress"]["selected_value"] == "42"
    assert metadata["metrics"]["stress"]["invalid_rows_skipped"] == 1
    assert metadata["metrics"]["stress"]["reason"] == ""


def test_garmindb_stress_reports_no_recent_rows_when_all_values_invalid(tmp_path):
    db_dir = tmp_path / "DBs"
    db_dir.mkdir()
    _create_garmin_db(db_dir / "garmin.db")
    with sqlite3.connect(db_dir / "garmin.db") as connection:
        connection.execute("DELETE FROM stress")
        connection.execute(
            "INSERT INTO stress (timestamp, stress) VALUES (?, ?)",
            ("2026-05-08 16:00:00", -2),
        )

    health_data, metadata = load_latest_health_data_with_metadata(db_dir=db_dir)

    assert health_data.stress == ""
    assert metadata["metrics"]["stress"]["raw_value"] == -2
    assert metadata["metrics"]["stress"]["selected_value"] == ""
    assert metadata["metrics"]["stress"]["invalid_rows_skipped"] == 1
    assert metadata["metrics"]["stress"]["reason"] == "no recent rows"


def test_garmindb_latest_directory_falls_back_to_monitoring_hr(tmp_path):
    db_dir = tmp_path / "DBs"
    db_dir.mkdir()
    _create_monitoring_db(db_dir / "garmin_monitoring.db", include_hr=True)

    with sqlite3.connect(db_dir / "garmin.db") as connection:
        connection.execute(
            """
            CREATE TABLE sleep (
                day DATETIME NOT NULL PRIMARY KEY,
                total_sleep TIME NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO sleep (day, total_sleep) VALUES (?, ?)",
            ("2026-05-07 00:00:00", "07:30:00.000000"),
        )

    health_data, metadata = load_latest_health_data_with_metadata(db_dir=db_dir)

    assert health_data.resting_hr == "54"
    assert metadata["metrics"]["resting_hr"]["table"] == "monitoring_hr"
    assert (
        metadata["metrics"]["resting_hr"]["semantic_source"]
        == "monitoring_heart_rate"
    )
    assert metadata["metrics"]["resting_hr"]["source_priority"] == "fallback"


def test_garmindb_hrv_direction_unknown_without_baseline(tmp_path):
    db_dir = tmp_path / "DBs"
    db_dir.mkdir()
    db_path = db_dir / "garmin.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE hrv (
                day DATETIME NOT NULL PRIMARY KEY,
                last_night_avg INTEGER,
                status VARCHAR
            )
            """
        )
        connection.execute(
            "INSERT INTO hrv (day, last_night_avg, status) VALUES (?, ?, ?)",
            ("2026-05-07 00:00:00", 31, "low"),
        )

    health_data, metadata = load_latest_health_data_with_metadata(db_dir=db_dir)

    assert health_data.hrv_status == "low"
    assert metadata["metrics"]["hrv_status"]["hrv_value"] == "31"
    assert metadata["metrics"]["hrv_status"]["hrv_unit"] == "ms"
    assert metadata["metrics"]["hrv_status"]["garmin_hrv_status"] == "low"
    assert metadata["metrics"]["hrv_status"]["hrv_balance"] == "unknown"
    assert metadata["metrics"]["hrv_status"]["hrv_risk"] == "unknown"
    assert "baseline range is unavailable" in metadata["metrics"]["hrv_status"][
        "hrv_message"
    ]
