import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
BOOTSTRAP_PATH = ROOT_DIR / "automation" / "bootstrap.py"


def _load_bootstrap_module():
    spec = importlib.util.spec_from_file_location("bootstrap", BOOTSTRAP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bootstrap_module = _load_bootstrap_module()


def test_bootstrap_creates_venv_installs_requirements_and_verifies_cli(
    tmp_path,
    monkeypatch,
):
    calls = []
    messages = []
    (tmp_path / "automation").mkdir()
    (tmp_path / "automation" / "setup_env.py").write_text("", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")

    def fake_run(command, check, env=None):
        calls.append({"command": command, "check": check, "env": env})

    monkeypatch.setattr(bootstrap_module.subprocess, "run", fake_run)

    result = bootstrap_module.bootstrap(project_dir=tmp_path, output=messages.append)

    venv_dir = tmp_path / ".venv"
    assert result == 0
    assert calls[0]["command"] == ["python3", "-m", "venv", str(venv_dir)]
    assert calls[0]["check"] is True
    assert calls[1]["command"] == [
        str(venv_dir / "bin" / "pip"),
        "install",
        "-r",
        str(tmp_path / "requirements.txt"),
    ]
    assert calls[1]["check"] is True
    assert calls[2]["command"] == [
        str(venv_dir / "bin" / "python"),
        str(tmp_path / "automation" / "setup_env.py"),
        "--allow-missing",
    ]
    assert calls[2]["check"] is True
    assert calls[3]["command"] == ["which", "garmindb_cli.py"]
    assert calls[3]["check"] is True
    assert calls[3]["env"]["VIRTUAL_ENV"] == str(venv_dir)
    assert str(venv_dir / "bin") in calls[3]["env"]["PATH"]
    assert "First bootstrap sync:" in messages
    assert (
        "  .venv/bin/python automation/run_garmindb_sync.py --timeout 0" in messages
    )
    assert "Morning scheduler:" in messages
    assert (
        "  .venv/bin/python automation/run_morning_scheduler.py "
        "--db-dir ~/HealthData/DBs"
        in messages
    )
    assert "garmindb_cli.py" not in "\n".join(messages)
    assert "python3 automation/run_garmindb_sync.py --timeout 0" not in "\n".join(
        messages
    )
    assert "python3 automation/run_morning_scheduler.py" not in "\n".join(messages)


def test_bootstrap_reuses_existing_venv_without_recreating_or_installing(
    tmp_path,
    monkeypatch,
):
    calls = []
    messages = []
    (tmp_path / ".venv").mkdir()
    (tmp_path / "automation").mkdir()
    (tmp_path / "automation" / "setup_env.py").write_text("", encoding="utf-8")

    def fake_run(command, check, env=None):
        calls.append({"command": command, "check": check, "env": env})

    monkeypatch.setattr(bootstrap_module.subprocess, "run", fake_run)

    result = bootstrap_module.bootstrap(project_dir=tmp_path, output=messages.append)

    assert result == 0
    assert len(calls) == 2
    assert calls[0]["command"] == [
        str(tmp_path / ".venv" / "bin" / "python"),
        str(tmp_path / "automation" / "setup_env.py"),
        "--allow-missing",
    ]
    assert calls[1]["command"] == ["which", "garmindb_cli.py"]
    assert "Reusing existing .venv; it will not be recreated." in messages


def test_bootstrap_interactive_passes_interactive_to_setup_env(tmp_path, monkeypatch):
    calls = []
    messages = []
    (tmp_path / ".venv").mkdir()
    (tmp_path / "automation").mkdir()
    (tmp_path / "automation" / "setup_env.py").write_text("", encoding="utf-8")

    def fake_run(command, check, env=None):
        calls.append({"command": command, "check": check, "env": env})

    monkeypatch.setattr(bootstrap_module.subprocess, "run", fake_run)

    result = bootstrap_module.bootstrap(
        project_dir=tmp_path,
        output=messages.append,
        interactive=True,
    )

    assert result == 0
    assert calls[0]["command"] == [
        str(tmp_path / ".venv" / "bin" / "python"),
        str(tmp_path / "automation" / "setup_env.py"),
        "--allow-missing",
        "--interactive",
    ]
