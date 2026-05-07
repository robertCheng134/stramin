import sqlite3
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from integrations.garmindb import GarminDBImportError, load_health_data


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
