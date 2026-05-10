import importlib.util
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parent.parent
AUTOMATION_DIR = ROOT_DIR / "automation"

sys.path.insert(0, str(AUTOMATION_DIR))


def _load_module(name):
    spec = importlib.util.spec_from_file_location(name, AUTOMATION_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_daily_state_module = _load_module("build_daily_state")
run_daily_pipeline_module = _load_module("run_daily_pipeline")
validate_health_data_module = _load_module("validate_health_data")


def _create_valid_garmindb(db_dir, day="2026-05-10"):
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "garmin.db"
    with sqlite3.connect(db_path) as connection:
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
            CREATE TABLE daily_summary (
                day DATETIME NOT NULL PRIMARY KEY
            )
            """
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
            (f"{day} 00:00:00", 42, 56, 35, 55, "balanced"),
        )
        connection.execute(
            "INSERT INTO sleep (day, total_sleep) VALUES (?, ?)",
            (f"{day} 00:00:00", "07:30:00.000000"),
        )
        connection.execute(
            "INSERT INTO stress (timestamp, stress) VALUES (?, ?)",
            (f"{day} 16:00:00", 28),
        )
        connection.execute(
            "INSERT INTO resting_hr (day, resting_heart_rate) VALUES (?, ?)",
            (f"{day} 00:00:00", 58.0),
        )
        connection.execute(
            "INSERT INTO daily_summary (day) VALUES (?)",
            (f"{day} 00:00:00",),
        )
    return db_path


def test_build_daily_state_writes_atomic_json(tmp_path, monkeypatch):
    output = tmp_path / "daily_state.json"
    log_dir = tmp_path / "logs"

    monkeypatch.setattr(
        build_daily_state_module,
        "build_recommendation_preview",
        lambda db_dir: {
            "health_data": type(
                "HealthData",
                (),
                {
                    "date": "2026-05-10",
                    "sleep_hours": "7.0",
                    "hrv_status": "balanced",
                    "resting_hr": "62",
                    "stress": "20",
                },
            )(),
            "metadata": {
                "source_date": "2026-05-10",
                "metrics": {
                    "hrv_status": {
                        "hrv_value": "32",
                        "hrv_5min_high": "43",
                        "hrv_balance": "below_baseline",
                    }
                },
            },
            "recovery_result": {"recovery_score": 80, "recovery_level": "good"},
            "decision": {"decision": "train"},
            "recommendation": "train / normal / walking",
            "rationale": "Ready.",
        },
    )

    state = build_daily_state_module.build_daily_state(
        db_dir=tmp_path,
        output=output,
        log_dir=log_dir,
    )

    assert output.exists()
    assert not output.with_suffix(".json.tmp").exists()
    written_state = json.loads(output.read_text(encoding="utf-8"))
    assert written_state["recommendation"] == "train / normal / walking"
    assert written_state["date"] == "2026-05-10"
    assert written_state["hrv"]["hrv_value"] == "32"
    assert written_state["recovery_state"]["recovery_level"] == "good"
    assert written_state["resting_hr"] == "62"
    assert state["latest_recovery_date"] == "2026-05-10"
    assert (log_dir / "pipeline.log").exists()


def test_validate_garmindb_fails_missing_database(tmp_path):
    with pytest.raises(
        validate_health_data_module.GarminDBImportError,
        match="missing GarminDB database",
    ):
        validate_health_data_module.validate_garmindb(db_dir=tmp_path)


def test_validate_garmindb_fails_empty_core_table(tmp_path):
    db_dir = tmp_path / "DBs"
    db_dir.mkdir()
    with sqlite3.connect(db_dir / "garmin.db") as connection:
        connection.execute("CREATE TABLE hrv (day TEXT)")
        connection.execute("CREATE TABLE sleep (day TEXT)")
        connection.execute("CREATE TABLE stress (timestamp TEXT, stress INTEGER)")
        connection.execute("CREATE TABLE daily_summary (day TEXT)")
        connection.execute("INSERT INTO sleep (day) VALUES ('2026-05-10')")
        connection.execute("INSERT INTO daily_summary (day) VALUES ('2026-05-10')")

    with pytest.raises(
        validate_health_data_module.GarminDBImportError,
        match="table hrv is empty",
    ):
        validate_health_data_module.validate_garmindb(db_dir=db_dir)


def test_validate_garmindb_passes_today(tmp_path, monkeypatch):
    db_dir = tmp_path / "DBs"
    _create_valid_garmindb(db_dir, day="2026-05-10")
    monkeypatch.setattr(validate_health_data_module, "today_iso", lambda: "2026-05-10")

    result = validate_health_data_module.validate_garmindb(
        db_dir=db_dir,
        log_dir=tmp_path / "logs",
    )

    assert result["status"] == "ready"
    assert result["latest_recovery_date"] == "2026-05-10"
    assert result["is_stale"] is False
    assert result["days_old"] == 0
    assert result["table_counts"]["hrv"] == 1


def test_validate_garmindb_passes_yesterday(tmp_path, monkeypatch):
    db_dir = tmp_path / "DBs"
    _create_valid_garmindb(db_dir, day="2026-05-09")
    monkeypatch.setattr(validate_health_data_module, "today_iso", lambda: "2026-05-10")

    result = validate_health_data_module.validate_garmindb(
        db_dir=db_dir,
        log_dir=tmp_path / "logs",
    )

    assert result["status"] == "ready"
    assert result["latest_recovery_date"] == "2026-05-09"
    assert result["is_stale"] is False
    assert result["days_old"] == 1


def test_validate_garmindb_fails_two_days_old_latest_data(tmp_path, monkeypatch):
    db_dir = tmp_path / "DBs"
    _create_valid_garmindb(db_dir, day="2026-05-08")
    monkeypatch.setattr(validate_health_data_module, "today_iso", lambda: "2026-05-10")

    with pytest.raises(
        validate_health_data_module.GarminDBImportError,
        match="latest recovery date 2026-05-08 is too stale; current date is 2026-05-10",
    ):
        validate_health_data_module.validate_garmindb(db_dir=db_dir)


def test_run_daily_pipeline_validation_failure_before_cutoff_is_retryable(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "daily_state.json"
    notification_state = tmp_path / "notification_state.json"

    monkeypatch.setattr(
        run_daily_pipeline_module,
        "sync_garmindb",
        lambda log_dir: {"status": "skipped_manual_sync_required"},
    )

    def fail_validation(**kwargs):
        raise run_daily_pipeline_module.GarminDBImportError("validation failed")

    monkeypatch.setattr(run_daily_pipeline_module, "validate_garmindb", fail_validation)

    result = run_daily_pipeline_module.run_daily_pipeline(
        db_dir=tmp_path,
        output=output,
        log_dir=tmp_path / "logs",
        notification_state_path=notification_state,
        current_datetime=datetime.fromisoformat("2026-05-10T09:10:00+08:00"),
    )

    assert result["status"] == "retryable"
    assert result["retryable"] is True
    assert result["retry_interval_minutes"] == 5
    assert result["telegram_sent"] is False
    assert not output.exists()
    written_state = json.loads(notification_state.read_text(encoding="utf-8"))
    assert written_state["retry_count"] == 1
    assert written_state["telegram_sent"] is False


def test_run_daily_pipeline_validation_failure_after_cutoff_is_final_failure(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "daily_state.json"
    notification_state = tmp_path / "notification_state.json"

    monkeypatch.setattr(
        run_daily_pipeline_module,
        "sync_garmindb",
        lambda log_dir: {"status": "skipped_manual_sync_required"},
    )

    def fail_validation(**kwargs):
        raise run_daily_pipeline_module.GarminDBImportError("validation failed")

    monkeypatch.setattr(run_daily_pipeline_module, "validate_garmindb", fail_validation)

    result = run_daily_pipeline_module.run_daily_pipeline(
        db_dir=tmp_path,
        output=output,
        log_dir=tmp_path / "logs",
        notification_state_path=notification_state,
        current_datetime=datetime.fromisoformat("2026-05-10T11:05:00+08:00"),
    )

    assert result["status"] == "final_failure"
    assert result["retryable"] is False
    assert result["telegram_sent"] is False
    assert "after cutoff" in result["telegram_reason"]
    assert not output.exists()
    written_state = json.loads(notification_state.read_text(encoding="utf-8"))
    assert written_state["retry_count"] == 1
    assert written_state["final_failure_sent"] is False


def test_run_daily_pipeline_noops_when_report_already_sent_today(
    tmp_path,
    monkeypatch,
):
    notification_state = tmp_path / "notification_state.json"
    notification_state.write_text(
        json.dumps(
            {
                "date": "2026-05-10",
                "telegram_sent": True,
                "sent_at": "2026-05-10T09:01:00+08:00",
                "last_attempt_at": "2026-05-10T09:01:00+08:00",
                "retry_count": 0,
                "final_failure_sent": False,
            }
        ),
        encoding="utf-8",
    )

    def fail_if_called(**kwargs):
        raise AssertionError("pipeline should no-op before validation")

    monkeypatch.setattr(run_daily_pipeline_module, "validate_garmindb", fail_if_called)

    result = run_daily_pipeline_module.run_daily_pipeline(
        db_dir=tmp_path,
        output=tmp_path / "daily_state.json",
        log_dir=tmp_path / "logs",
        notification_state_path=notification_state,
        current_datetime=datetime.fromisoformat("2026-05-10T09:30:00+08:00"),
    )

    assert result["status"] == "already_sent"
    assert result["telegram_sent"] is False
    assert "already sent" in result["telegram_reason"]


def test_run_daily_pipeline_builds_state_without_telegram(tmp_path, monkeypatch):
    output = tmp_path / "daily_state.json"
    log_dir = tmp_path / "logs"

    monkeypatch.setattr(
        run_daily_pipeline_module,
        "sync_garmindb",
        lambda log_dir: {"status": "skipped_manual_sync_required"},
    )
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "validate_garmindb",
        lambda **kwargs: {
            "status": "ready",
            "latest_recovery_date": "2026-05-10",
            "is_stale": False,
        },
    )
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "build_daily_state",
        lambda **kwargs: {
            "latest_recovery_date": "2026-05-10",
            "recommendation": "train / normal / walking",
            "rationale": "Ready.",
            "decision": {"decision": "train"},
        },
    )

    result = run_daily_pipeline_module.run_daily_pipeline(
        db_dir=tmp_path,
        output=output,
        log_dir=log_dir,
        notification_state_path=tmp_path / "notification_state.json",
        dry_run=True,
        current_datetime=datetime.fromisoformat("2026-05-10T09:00:00+08:00"),
    )

    assert result["status"] == "ready"
    assert result["dry_run"] is True
    assert result["telegram_sent"] is False
    assert "no Telegram message sent" in result["telegram_reason"]
    assert result["recommendation_preview"]["recommendation"] == (
        "train / normal / walking"
    )
    assert result["notification_state"]["telegram_sent"] is False
    assert not (tmp_path / "notification_state.json").exists()
    assert (log_dir / "pipeline.log").exists()
