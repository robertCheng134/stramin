from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def test_onboarding_docs_do_not_recommend_raw_infinite_loops():
    paths = [
        ROOT_DIR / "README.md",
        ROOT_DIR / "docs" / "first-run-onboarding.md",
        ROOT_DIR / "docs" / "v4-automation-design.md",
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "while true" not in text
        assert "sleep 300" not in text


def test_first_run_onboarding_uses_stramin_level_commands():
    text = (ROOT_DIR / "docs" / "first-run-onboarding.md").read_text(
        encoding="utf-8"
    )

    assert "python3 automation/bootstrap.py --interactive" in text
    assert ".venv/bin/python automation/run_garmindb_sync.py --timeout 0" in text
    assert (
        ".venv/bin/python automation/run_morning_scheduler.py "
        "--db-dir ~/HealthData/DBs"
    ) in (
        text
    )
    assert "python3 automation/run_garmindb_sync.py --timeout 0" not in text
    assert "python3 automation/run_morning_scheduler.py" not in text
    assert "garmindb_cli.py" not in text
