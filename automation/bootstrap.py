import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def _venv_bin_dir(venv_dir):
    return venv_dir / ("Scripts" if os.name == "nt" else "bin")


def _venv_command(venv_dir, name):
    suffix = ".exe" if os.name == "nt" and name in {"python", "pip"} else ""
    return str(_venv_bin_dir(venv_dir) / f"{name}{suffix}")


def _venv_env(venv_dir):
    env = os.environ.copy()
    bin_dir = str(_venv_bin_dir(venv_dir))
    env["VIRTUAL_ENV"] = str(venv_dir)
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    return env


def bootstrap(project_dir=ROOT_DIR, output=print):
    project_path = Path(project_dir)
    venv_dir = project_path / ".venv"
    requirements = project_path / "requirements.txt"
    setup_env_script = project_path / "automation" / "setup_env.py"

    output("Starting Stramin first-run bootstrap...")

    if venv_dir.exists():
        output("Reusing existing .venv; it will not be recreated.")
    else:
        output("Creating .venv...")
        subprocess.run(["python3", "-m", "venv", str(venv_dir)], check=True)
        output("Installing requirements.txt...")
        subprocess.run(
            [_venv_command(venv_dir, "pip"), "install", "-r", str(requirements)],
            check=True,
        )

    output("Creating or validating .env...")
    subprocess.run(
        [_venv_command(venv_dir, "python"), str(setup_env_script), "--allow-missing"],
        check=True,
    )

    output("Verifying GarminDB CLI in the virtualenv...")
    subprocess.run(
        ["which", "garmindb_cli.py"],
        check=True,
        env=_venv_env(venv_dir),
    )

    output("")
    output("Next steps:")
    output("First bootstrap sync:")
    output("  python3 automation/run_garmindb_sync.py --timeout 0")
    output("")
    output("Daily operation:")
    output(
        "  python3 automation/run_daily_pipeline.py "
        "--sync-garmin --db-dir ~/HealthData/DBs"
    )
    return 0


def main():
    return bootstrap()


if __name__ == "__main__":
    raise SystemExit(main())
