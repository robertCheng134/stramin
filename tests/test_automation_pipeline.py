import importlib.util
import json
import sys
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
    assert json.loads(output.read_text(encoding="utf-8"))["recommendation"] == (
        "train / normal / walking"
    )
    assert state["latest_recovery_date"] == "2026-05-10"
    assert (log_dir / "daily-state.log").exists()


def test_validate_garmindb_fails_missing_database(tmp_path):
    with pytest.raises(validate_health_data_module.GarminDBImportError):
        validate_health_data_module.validate_garmindb(db_dir=tmp_path)


def test_run_daily_pipeline_fails_when_validation_fails(tmp_path, monkeypatch):
    output = tmp_path / "daily_state.json"

    monkeypatch.setattr(
        run_daily_pipeline_module,
        "sync_garmindb",
        lambda log_dir: {"status": "skipped_manual_sync_required"},
    )

    def fail_validation(**kwargs):
        raise run_daily_pipeline_module.GarminDBImportError("validation failed")

    monkeypatch.setattr(run_daily_pipeline_module, "validate_garmindb", fail_validation)

    with pytest.raises(run_daily_pipeline_module.GarminDBImportError):
        run_daily_pipeline_module.run_daily_pipeline(
            db_dir=tmp_path,
            output=output,
            log_dir=tmp_path / "logs",
        )

    assert not output.exists()


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
        },
    )

    result = run_daily_pipeline_module.run_daily_pipeline(
        db_dir=tmp_path,
        output=output,
        log_dir=log_dir,
    )

    assert result["status"] == "ready"
    assert result["telegram_sent"] is False
    assert "no message sent" in result["telegram_reason"]
