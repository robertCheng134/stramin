import importlib.util
import sqlite3
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "preview_garmindb_recommendation.py"
)

spec = importlib.util.spec_from_file_location(
    "preview_garmindb_recommendation",
    SCRIPT_PATH,
)
preview_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview_script)


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
            ("2026-05-07 00:00:00", 37, 52, 35, 39, "balanced"),
        )


def test_build_recommendation_preview_uses_garmindb_health_data(tmp_path):
    db_dir = tmp_path / "DBs"
    db_dir.mkdir()
    _create_garmin_db(db_dir / "garmin.db")

    preview = preview_script.build_recommendation_preview(db_dir)

    assert preview["metadata"]["source_date"] == "2026-05-07"
    assert preview["health_data"].sleep_hours == "7.5"
    assert preview["health_data"].stress == "42"
    assert preview["metadata"]["metrics"]["hrv_status"]["hrv_value"] == "37"
    assert preview["metadata"]["metrics"]["hrv_status"]["hrv_5min_high"] == "52"
    assert preview["metadata"]["metrics"]["hrv_status"]["hrv_balance"] == "within_baseline"
    assert preview["metadata"]["metrics"]["hrv_status"]["hrv_risk"] == "stable"
    assert preview["decision"]["decision"] in {
        "train",
        "light_training",
        "recovery_day",
        "rest",
    }
    assert "Body Battery was unavailable" in preview["rationale"]


def test_print_preview_outputs_required_fields(tmp_path, capsys):
    db_dir = tmp_path / "DBs"
    db_dir.mkdir()
    _create_garmin_db(db_dir / "garmin.db")

    preview = preview_script.build_recommendation_preview(db_dir)
    preview_script.print_preview(preview)

    output = capsys.readouterr().out
    assert "latest_recovery_date=2026-05-07" in output
    assert "sleep_hours=7.5" in output
    assert "hrv_value=37" in output
    assert "hrv_5min_high=52" in output
    assert "hrv_balance=Within baseline" in output
    assert "hrv_risk" not in output
    assert "resting_hr=62" in output
    assert "stress=42" in output
    assert "recommendation=" in output
    assert "rationale=" in output


def test_print_preview_omits_empty_stress(tmp_path, capsys):
    db_dir = tmp_path / "DBs"
    db_dir.mkdir()
    _create_garmin_db(db_dir / "garmin.db")
    with sqlite3.connect(db_dir / "garmin.db") as connection:
        connection.execute("DELETE FROM stress")
        connection.execute(
            "INSERT INTO stress (timestamp, stress) VALUES (?, ?)",
            ("2026-05-08 16:00:00", -2),
        )

    preview = preview_script.build_recommendation_preview(db_dir)
    preview_script.print_preview(preview)

    output = capsys.readouterr().out
    assert preview["health_data"].stress == ""
    assert "stress=" not in output
