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
run_garmindb_sync_module = _load_module("run_garmindb_sync")
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


def test_garmindb_sync_command_is_latest_only(monkeypatch):
    monkeypatch.setattr(
        run_garmindb_sync_module,
        "resolve_garmindb_cli",
        lambda: "garmindb_cli.py",
    )
    command = run_garmindb_sync_module.build_sync_command()

    assert command == [
        "garmindb_cli.py",
        "--all",
        "--download",
        "--import",
        "--analyze",
        "--latest",
    ]
    assert "--latest" in command


def test_garmindb_sync_command_includes_required_steps(monkeypatch):
    monkeypatch.setattr(
        run_garmindb_sync_module,
        "resolve_garmindb_cli",
        lambda: "garmindb_cli.py",
    )
    command = run_garmindb_sync_module.build_sync_command()

    for flag in ["--all", "--download", "--import", "--analyze"]:
        assert flag in command


def test_run_garmindb_sync_success_returns_zero(monkeypatch, capsys):
    calls = []
    resolved_cli = "/repo/.venv/bin/garmindb_cli.py"

    def fake_run(command, timeout, check):
        calls.append({"command": command, "timeout": timeout, "check": check})

    monkeypatch.setattr(
        run_garmindb_sync_module,
        "resolve_garmindb_cli",
        lambda: resolved_cli,
    )
    monkeypatch.setattr(run_garmindb_sync_module.subprocess, "run", fake_run)

    exit_code = run_garmindb_sync_module.run_garmindb_sync(timeout=42)

    assert exit_code == 0
    assert calls == [
        {
            "command": [resolved_cli]
            + ["--all", "--download", "--import", "--analyze", "--latest"],
            "timeout": 42,
            "check": True,
        }
    ]
    assert "completed successfully" in capsys.readouterr().out


def test_garmindb_sync_prefers_venv_local_cli(tmp_path, monkeypatch):
    local_cli = tmp_path / ".venv" / "bin" / "garmindb_cli.py"
    local_cli.parent.mkdir(parents=True)
    local_cli.write_text("#!/usr/bin/env python\n", encoding="utf-8")
    monkeypatch.setattr(
        run_garmindb_sync_module.shutil,
        "which",
        lambda name: "/usr/local/bin/garmindb_cli.py",
    )

    resolved = run_garmindb_sync_module.resolve_garmindb_cli(root=tmp_path)

    assert resolved == str(local_cli)


def test_garmindb_sync_falls_back_to_path_when_venv_cli_missing(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        run_garmindb_sync_module.shutil,
        "which",
        lambda name: "/usr/local/bin/garmindb_cli.py",
    )

    resolved = run_garmindb_sync_module.resolve_garmindb_cli(root=tmp_path)

    assert resolved == "/usr/local/bin/garmindb_cli.py"


def test_run_garmindb_sync_timeout_zero_disables_timeout(monkeypatch):
    calls = []
    resolved_cli = "/repo/.venv/bin/garmindb_cli.py"

    def fake_run(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(
        run_garmindb_sync_module,
        "resolve_garmindb_cli",
        lambda: resolved_cli,
    )
    monkeypatch.setattr(run_garmindb_sync_module.subprocess, "run", fake_run)

    exit_code = run_garmindb_sync_module.run_garmindb_sync(timeout=0)

    assert exit_code == 0
    assert calls == [
        {
            "args": (
                [resolved_cli]
                + ["--all", "--download", "--import", "--analyze", "--latest"],
            ),
            "kwargs": {"check": True},
        }
    ]


def test_run_garmindb_sync_positive_timeout_passes_timeout(monkeypatch):
    calls = []
    resolved_cli = "/repo/.venv/bin/garmindb_cli.py"

    def fake_run(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(
        run_garmindb_sync_module,
        "resolve_garmindb_cli",
        lambda: resolved_cli,
    )
    monkeypatch.setattr(run_garmindb_sync_module.subprocess, "run", fake_run)

    exit_code = run_garmindb_sync_module.run_garmindb_sync(timeout=42)

    assert exit_code == 0
    assert calls == [
        {
            "args": (
                [resolved_cli]
                + ["--all", "--download", "--import", "--analyze", "--latest"],
            ),
            "kwargs": {"timeout": 42, "check": True},
        }
    ]


def test_run_garmindb_sync_failure_returns_nonzero(monkeypatch, capsys):
    def fake_run(command, timeout, check):
        raise run_garmindb_sync_module.subprocess.CalledProcessError(
            returncode=7,
            cmd=command,
        )

    monkeypatch.setattr(run_garmindb_sync_module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        run_garmindb_sync_module,
        "resolve_garmindb_cli",
        lambda: "/repo/.venv/bin/garmindb_cli.py",
    )

    exit_code = run_garmindb_sync_module.run_garmindb_sync(timeout=42)

    assert exit_code == 7
    assert "failed with exit code 7" in capsys.readouterr().out


def test_run_garmindb_sync_missing_cli_returns_clear_error(monkeypatch, capsys):
    monkeypatch.setattr(run_garmindb_sync_module, "resolve_garmindb_cli", lambda: None)

    exit_code = run_garmindb_sync_module.run_garmindb_sync(timeout=42)

    assert exit_code == 127
    assert (
        "GarminDB CLI not found. Install dependencies with "
        "pip install -r requirements.txt."
    ) in capsys.readouterr().out


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


def test_build_daily_state_has_stable_latest_health_contract(tmp_path, monkeypatch):
    output = tmp_path / "daily_state.json"

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
                    "resting_hr": "",
                    "stress": "20",
                },
            )(),
            "metadata": {
                "source_date": "2026-05-10",
                "metrics": {"hrv_status": {"hrv_value": "42"}},
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
        log_dir=tmp_path / "logs",
    )

    for key in [
        "latest_recovery_date",
        "validation_status",
        "sleep_hours",
        "hrv",
        "stress",
        "resting_hr",
        "decision",
        "recommendation",
        "rationale",
    ]:
        assert key in state
    assert state["resting_hr"] == ""


def test_build_daily_state_reads_garmindb_sleep_for_recovery_date(tmp_path):
    db_dir = tmp_path / "DBs"
    db_dir.mkdir()
    with sqlite3.connect(db_dir / "garmin.db") as connection:
        connection.execute(
            """
            CREATE TABLE daily_summary (
                day DATETIME NOT NULL PRIMARY KEY,
                rhr INTEGER,
                stress_avg INTEGER,
                bb_charged INTEGER
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE sleep (
                day DATETIME NOT NULL PRIMARY KEY,
                total_sleep TIME NOT NULL,
                score INTEGER,
                avg_stress FLOAT,
                qualifier VARCHAR
            )
            """
        )
        connection.execute(
            """
            INSERT INTO daily_summary (day, rhr, stress_avg, bb_charged)
            VALUES (?, ?, ?, ?)
            """,
            ("2026-05-10 00:00:00.000000", 59, 20, 70),
        )
        connection.execute(
            """
            INSERT INTO sleep (day, total_sleep, score, avg_stress, qualifier)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("2026-05-10 00:00:00.000000", "07:26:00.000000", 87, 20.0, "GOOD"),
        )

    output = tmp_path / "daily_state.json"
    state = build_daily_state_module.build_daily_state(
        db_dir=db_dir,
        output=output,
        log_dir=tmp_path / "logs",
    )

    assert state["latest_recovery_date"] == "2026-05-10"
    assert state["sleep_hours"] == "7.43"
    assert json.loads(output.read_text(encoding="utf-8"))["sleep_hours"] == "7.43"


def test_validate_garmindb_fails_missing_database(tmp_path):
    with pytest.raises(
        validate_health_data_module.GarminDBImportError,
        match="missing GarminDB database",
    ):
        validate_health_data_module.validate_garmindb(db_dir=tmp_path)


def test_validate_garmindb_fails_empty_daily_summary(tmp_path):
    db_dir = tmp_path / "DBs"
    db_dir.mkdir()
    with sqlite3.connect(db_dir / "garmin.db") as connection:
        connection.execute("CREATE TABLE hrv (day TEXT)")
        connection.execute("CREATE TABLE sleep (day TEXT)")
        connection.execute("CREATE TABLE stress (timestamp TEXT, stress INTEGER)")
        connection.execute("CREATE TABLE daily_summary (day TEXT)")
        connection.execute("INSERT INTO sleep (day) VALUES ('2026-05-10')")

    with pytest.raises(
        validate_health_data_module.GarminDBImportError,
        match="table daily_summary is empty",
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


def test_validate_garmindb_uses_fresh_daily_summary_despite_stale_raw_tables(
    tmp_path,
    monkeypatch,
):
    db_dir = tmp_path / "DBs"
    db_dir.mkdir()
    with sqlite3.connect(db_dir / "garmin.db") as connection:
        connection.execute("CREATE TABLE hrv (day TEXT)")
        connection.execute("CREATE TABLE sleep (day TEXT, total_sleep TEXT)")
        connection.execute("CREATE TABLE stress (timestamp TEXT, stress INTEGER)")
        connection.execute("CREATE TABLE daily_summary (day TEXT)")
        connection.execute("INSERT INTO hrv (day) VALUES ('2026-05-01')")
        connection.execute(
            "INSERT INTO sleep (day, total_sleep) VALUES ('2026-05-01', '07:00:00')"
        )
        connection.execute("INSERT INTO daily_summary (day) VALUES ('2026-05-10')")
    monkeypatch.setattr(validate_health_data_module, "today_iso", lambda: "2026-05-10")

    result = validate_health_data_module.validate_garmindb(
        db_dir=db_dir,
        log_dir=tmp_path / "logs",
    )

    assert result["status"] == "ready"
    assert result["latest_recovery_date"] == "2026-05-10"
    assert result["is_stale"] is False


def test_validate_garmindb_fails_two_days_old_latest_data(tmp_path, monkeypatch):
    db_dir = tmp_path / "DBs"
    _create_valid_garmindb(db_dir, day="2026-05-08")
    monkeypatch.setattr(validate_health_data_module, "today_iso", lambda: "2026-05-10")

    with pytest.raises(
        validate_health_data_module.GarminDBImportError,
        match="latest recovery date 2026-05-08 is too stale; current date is 2026-05-10",
    ):
        validate_health_data_module.validate_garmindb(db_dir=db_dir)


def test_validate_garmindb_fails_future_latest_data(tmp_path, monkeypatch):
    db_dir = tmp_path / "DBs"
    _create_valid_garmindb(db_dir, day="2026-05-11")
    monkeypatch.setattr(validate_health_data_module, "today_iso", lambda: "2026-05-10")

    with pytest.raises(
        validate_health_data_module.GarminDBImportError,
        match="latest recovery date 2026-05-11 is in the future; current date is 2026-05-10",
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
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "send_message",
        lambda text: {"success": False, "reason": "not_sent"},
    )

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
    sent_messages = []
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "send_message",
        lambda text: sent_messages.append(text) or {"success": True, "message": "sent"},
    )

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
    assert sent_messages
    assert "No training recommendation was sent." in sent_messages[0]
    assert "Recommendation\n" not in sent_messages[0]
    written_state = json.loads(notification_state.read_text(encoding="utf-8"))
    assert written_state["retry_count"] == 1
    assert written_state["final_failure_sent"] is True


def test_run_daily_pipeline_final_failure_warning_sends_once_per_local_date(
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
    sent_messages = []
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "send_message",
        lambda text: sent_messages.append(text) or {"success": True, "message": "sent"},
    )

    first_result = run_daily_pipeline_module.run_daily_pipeline(
        db_dir=tmp_path,
        output=output,
        log_dir=tmp_path / "logs",
        notification_state_path=notification_state,
        current_datetime=datetime.fromisoformat("2026-05-10T11:05:00+08:00"),
    )
    second_result = run_daily_pipeline_module.run_daily_pipeline(
        db_dir=tmp_path,
        output=output,
        log_dir=tmp_path / "logs",
        notification_state_path=notification_state,
        current_datetime=datetime.fromisoformat("2026-05-10T11:10:00+08:00"),
    )

    assert first_result["status"] == "final_failure"
    assert second_result["status"] == "final_failure"
    assert len(sent_messages) == 1
    assert second_result["telegram_send_result"]["reason"] == "already_sent"
    written_state = json.loads(notification_state.read_text(encoding="utf-8"))
    assert written_state["retry_count"] == 2
    assert written_state["final_failure_sent"] is True


def test_run_daily_pipeline_final_failure_warning_can_send_next_local_date(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "daily_state.json"
    notification_state = tmp_path / "notification_state.json"
    notification_state.write_text(
        json.dumps(
            {
                "date": "2026-05-10",
                "telegram_sent": False,
                "sent_at": "",
                "last_attempt_at": "",
                "retry_count": 1,
                "final_failure_sent": True,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        run_daily_pipeline_module,
        "sync_garmindb",
        lambda log_dir: {"status": "skipped_manual_sync_required"},
    )

    def fail_validation(**kwargs):
        raise run_daily_pipeline_module.GarminDBImportError("validation failed")

    monkeypatch.setattr(run_daily_pipeline_module, "validate_garmindb", fail_validation)
    sent_messages = []
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "send_message",
        lambda text: sent_messages.append(text) or {"success": True, "message": "sent"},
    )

    result = run_daily_pipeline_module.run_daily_pipeline(
        db_dir=tmp_path,
        output=output,
        log_dir=tmp_path / "logs",
        notification_state_path=notification_state,
        current_datetime=datetime.fromisoformat("2026-05-11T11:05:00+08:00"),
    )

    assert result["status"] == "final_failure"
    assert len(sent_messages) == 1
    written_state = json.loads(notification_state.read_text(encoding="utf-8"))
    assert written_state["date"] == "2026-05-11"
    assert written_state["retry_count"] == 1
    assert written_state["final_failure_sent"] is True


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
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "run_garmindb_sync",
        lambda: pytest.fail("default duplicate no-op must not sync GarminDB"),
    )

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


def test_run_daily_pipeline_sync_garmin_runs_before_already_sent_noop(
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
    call_order = []

    monkeypatch.setattr(
        run_daily_pipeline_module,
        "run_garmindb_sync",
        lambda: call_order.append("sync") or 0,
    )
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "validate_garmindb",
        lambda **kwargs: pytest.fail("already-sent no-op must not validate"),
    )
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "send_message",
        lambda text: pytest.fail("already-sent no-op must not send Telegram"),
    )

    result = run_daily_pipeline_module.run_daily_pipeline(
        db_dir=tmp_path,
        output=tmp_path / "daily_state.json",
        log_dir=tmp_path / "logs",
        notification_state_path=notification_state,
        sync_garmin=True,
        current_datetime=datetime.fromisoformat("2026-05-10T09:30:00+08:00"),
    )

    assert call_order == ["sync"]
    assert result["status"] == "already_sent"
    assert result["telegram_sent"] is False
    assert result["sync"]["status"] == "completed"
    assert "already sent" in result["telegram_reason"]


def test_run_daily_pipeline_default_does_not_run_managed_sync(tmp_path, monkeypatch):
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "run_garmindb_sync",
        lambda: pytest.fail("managed sync should only run with sync_garmin=True"),
    )
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
            "sleep_hours": "7.0",
            "hrv": {"hrv_value": "42", "hrv_unit": "ms", "hrv_balance": "stable"},
            "stress": "20",
            "resting_hr": "58",
            "recommendation": "train / normal / walking",
            "rationale": "Ready.",
            "decision": {"decision": "train"},
        },
    )

    result = run_daily_pipeline_module.run_daily_pipeline(
        db_dir=tmp_path,
        output=tmp_path / "daily_state.json",
        log_dir=tmp_path / "logs",
        notification_state_path=tmp_path / "notification_state.json",
        dry_run=True,
        current_datetime=datetime.fromisoformat("2026-05-10T09:00:00+08:00"),
    )

    assert result["status"] == "ready"
    assert result["state"]["sync"]["status"] == "skipped_manual_sync_required"


def test_run_daily_pipeline_sync_garmin_runs_before_validation(tmp_path, monkeypatch):
    call_order = []

    monkeypatch.setattr(
        run_daily_pipeline_module,
        "run_garmindb_sync",
        lambda: call_order.append("sync") or 0,
    )
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "validate_garmindb",
        lambda **kwargs: call_order.append("validation")
        or {
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
            "sleep_hours": "7.0",
            "hrv": {"hrv_value": "42", "hrv_unit": "ms", "hrv_balance": "stable"},
            "stress": "20",
            "resting_hr": "58",
            "recommendation": "train / normal / walking",
            "rationale": "Ready.",
            "decision": {"decision": "train"},
        },
    )

    result = run_daily_pipeline_module.run_daily_pipeline(
        db_dir=tmp_path,
        output=tmp_path / "daily_state.json",
        log_dir=tmp_path / "logs",
        notification_state_path=tmp_path / "notification_state.json",
        dry_run=True,
        sync_garmin=True,
        current_datetime=datetime.fromisoformat("2026-05-10T09:00:00+08:00"),
    )

    assert result["status"] == "ready"
    assert result["state"]["sync"]["status"] == "completed"
    assert call_order[:2] == ["sync", "validation"]


def test_run_daily_pipeline_sync_failure_prevents_validation_and_telegram(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(run_daily_pipeline_module, "run_garmindb_sync", lambda: 7)
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "validate_garmindb",
        lambda **kwargs: pytest.fail("validation must not run after sync failure"),
    )
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "send_message",
        lambda text: pytest.fail("Telegram must not send after sync failure"),
    )

    result = run_daily_pipeline_module.run_daily_pipeline(
        db_dir=tmp_path,
        output=tmp_path / "daily_state.json",
        log_dir=tmp_path / "logs",
        notification_state_path=tmp_path / "notification_state.json",
        sync_garmin=True,
        current_datetime=datetime.fromisoformat("2026-05-10T09:00:00+08:00"),
    )

    assert result["status"] == "sync_failed"
    assert result["retryable"] is True
    assert result["telegram_sent"] is False
    assert result["sync"]["exit_code"] == 7


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
            "sleep_hours": "7.0",
            "hrv": {"hrv_value": "42", "hrv_unit": "ms", "hrv_balance": "stable"},
            "stress": "20",
            "resting_hr": "58",
            "recommendation": "train / normal / walking",
            "rationale": "Ready.",
            "decision": {
                "decision": "train",
                "intensity": "normal",
                "suggested_activity": "walking",
            },
        },
    )
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "send_message",
        lambda text: pytest.fail("dry-run must not send Telegram"),
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
    assert "🌅 Stramin Daily Recovery" in result["telegram_message"]
    assert "Sleep: 7.0h" in result["telegram_message"]
    assert result["notification_state"]["telegram_sent"] is False
    assert not (tmp_path / "notification_state.json").exists()
    assert (log_dir / "pipeline.log").exists()


def test_run_daily_pipeline_dry_run_with_sync_does_not_send_telegram(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(run_daily_pipeline_module, "run_garmindb_sync", lambda: 0)
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
            "sleep_hours": "7.0",
            "hrv": {"hrv_value": "42", "hrv_unit": "ms", "hrv_balance": "stable"},
            "stress": "20",
            "resting_hr": "58",
            "recommendation": "train / normal / walking",
            "rationale": "Ready.",
            "decision": {"decision": "train"},
        },
    )
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "send_message",
        lambda text: pytest.fail("dry-run + sync must not send Telegram"),
    )

    result = run_daily_pipeline_module.run_daily_pipeline(
        db_dir=tmp_path,
        output=tmp_path / "daily_state.json",
        log_dir=tmp_path / "logs",
        notification_state_path=tmp_path / "notification_state.json",
        dry_run=True,
        sync_garmin=True,
        current_datetime=datetime.fromisoformat("2026-05-10T09:00:00+08:00"),
    )

    assert result["status"] == "ready"
    assert result["telegram_sent"] is False
    assert result["state"]["sync"]["status"] == "completed"


def test_run_daily_pipeline_successful_send_marks_telegram_sent(
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
            "sleep_hours": "7.0",
            "hrv": {"hrv_value": "42", "hrv_unit": "ms", "hrv_balance": "stable"},
            "stress": "20",
            "resting_hr": "58",
            "recommendation": "train / normal / walking",
            "rationale": "Ready.",
            "decision": {
                "decision": "train",
                "intensity": "normal",
                "suggested_activity": "walking",
            },
        },
    )
    sent_messages = []
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "send_message",
        lambda text: sent_messages.append(text) or {"success": True, "message": "sent"},
    )

    result = run_daily_pipeline_module.run_daily_pipeline(
        db_dir=tmp_path,
        output=output,
        log_dir=tmp_path / "logs",
        notification_state_path=notification_state,
        current_datetime=datetime.fromisoformat("2026-05-10T09:00:00+08:00"),
    )

    assert result["status"] == "ready"
    assert result["telegram_sent"] is True
    assert sent_messages
    written_state = json.loads(notification_state.read_text(encoding="utf-8"))
    assert written_state["telegram_sent"] is True
    assert written_state["sent_at"]


def test_run_daily_pipeline_loads_dotenv_before_telegram_send(tmp_path, monkeypatch):
    call_order = []

    monkeypatch.setattr(
        run_daily_pipeline_module,
        "load_dotenv",
        lambda path: call_order.append(("dotenv", path)) or True,
    )
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
            "sleep_hours": "7.0",
            "hrv": {"hrv_value": "42", "hrv_unit": "ms", "hrv_balance": "stable"},
            "stress": "20",
            "resting_hr": "58",
            "recommendation": "train / normal / walking",
            "rationale": "Ready.",
            "decision": {
                "decision": "train",
                "intensity": "normal",
                "suggested_activity": "walking",
            },
        },
    )
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "send_message",
        lambda text: call_order.append(("send", text))
        or {"success": True, "message": "sent"},
    )

    result = run_daily_pipeline_module.run_daily_pipeline(
        db_dir=tmp_path,
        output=tmp_path / "daily_state.json",
        log_dir=tmp_path / "logs",
        notification_state_path=tmp_path / "notification_state.json",
        current_datetime=datetime.fromisoformat("2026-05-10T09:00:00+08:00"),
    )

    assert result["telegram_sent"] is True
    assert call_order[0] == ("dotenv", ".env")
    assert call_order[1][0] == "send"


def test_main_prints_actual_telegram_sent_result(monkeypatch, capsys):
    args = type(
        "Args",
        (),
        {
            "db_dir": "db",
            "output": "daily_state.json",
            "log_dir": "logs",
            "notification_state": "notification_state.json",
            "allow_stale": False,
            "dry_run": False,
            "sync_garmin": False,
            "daily_report_time": "09:00",
            "retry_interval_minutes": 5,
            "cutoff_time": "11:00",
        },
    )()
    monkeypatch.setattr(run_daily_pipeline_module, "parse_args", lambda: args)
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "run_daily_pipeline",
        lambda **kwargs: {
            "status": "ready",
            "telegram_sent": True,
            "state": {"latest_recovery_date": "2026-05-10"},
        },
    )

    exit_code = run_daily_pipeline_module.main()

    assert exit_code == 0
    assert (
        "Daily pipeline ready: latest_recovery_date=2026-05-10; telegram_sent=true"
        in capsys.readouterr().out
    )


def test_main_prints_false_for_dry_run_result(monkeypatch, capsys):
    args = type(
        "Args",
        (),
        {
            "db_dir": "db",
            "output": "daily_state.json",
            "log_dir": "logs",
            "notification_state": "notification_state.json",
            "allow_stale": False,
            "dry_run": True,
            "sync_garmin": False,
            "daily_report_time": "09:00",
            "retry_interval_minutes": 5,
            "cutoff_time": "11:00",
        },
    )()
    monkeypatch.setattr(run_daily_pipeline_module, "parse_args", lambda: args)
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "run_daily_pipeline",
        lambda **kwargs: {
            "status": "ready",
            "telegram_sent": False,
            "state": {"latest_recovery_date": "2026-05-10"},
        },
    )

    exit_code = run_daily_pipeline_module.main()

    assert exit_code == 0
    assert (
        "Daily pipeline ready: latest_recovery_date=2026-05-10; telegram_sent=false"
        in capsys.readouterr().out
    )


def test_main_returns_retryable_code_for_sync_failure(monkeypatch, capsys):
    args = type(
        "Args",
        (),
        {
            "db_dir": "db",
            "output": "daily_state.json",
            "log_dir": "logs",
            "notification_state": "notification_state.json",
            "allow_stale": False,
            "dry_run": False,
            "sync_garmin": True,
            "daily_report_time": "09:00",
            "retry_interval_minutes": 5,
            "cutoff_time": "11:00",
        },
    )()
    monkeypatch.setattr(run_daily_pipeline_module, "parse_args", lambda: args)
    monkeypatch.setattr(
        run_daily_pipeline_module,
        "run_daily_pipeline",
        lambda **kwargs: {
            "status": "sync_failed",
            "retryable": True,
            "telegram_sent": False,
            "sync": {"exit_code": 7},
        },
    )

    exit_code = run_daily_pipeline_module.main()

    assert exit_code == 2
    output = capsys.readouterr().out
    assert "Daily pipeline sync failed retryable" in output
    assert "exit_code=7" in output
    assert "telegram_sent=false" in output
