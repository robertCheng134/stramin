import argparse
import shutil
import subprocess
from pathlib import Path


CLI_NAME = "garmindb_cli.py"
SYNC_FLAGS = ["--all", "--download", "--import", "--analyze", "--latest"]
DEFAULT_TIMEOUT_SECONDS = 1800


def project_root():
    return Path(__file__).resolve().parent.parent


def venv_cli_path(root=None):
    root_path = Path(root) if root else project_root()
    return root_path / ".venv" / "bin" / CLI_NAME


def resolve_garmindb_cli(root=None):
    local_cli = venv_cli_path(root)
    if local_cli.exists():
        return str(local_cli)
    return shutil.which(CLI_NAME)


def build_sync_command():
    cli = resolve_garmindb_cli()
    if cli is None:
        cli = CLI_NAME
    return [cli] + list(SYNC_FLAGS)


def run_garmindb_sync(timeout=DEFAULT_TIMEOUT_SECONDS):
    command = build_sync_command()
    print("Starting GarminDB latest sync...")
    print("Command: " + " ".join(command))

    try:
        if command[0] == CLI_NAME and resolve_garmindb_cli() is None:
            raise FileNotFoundError(CLI_NAME)
        if timeout <= 0:
            subprocess.run(command, check=True)
        else:
            subprocess.run(command, timeout=timeout, check=True)
    except FileNotFoundError:
        print(
            "GarminDB CLI not found. Install dependencies with "
            "pip install -r requirements.txt."
        )
        return 127
    except subprocess.TimeoutExpired:
        print(f"GarminDB sync failed: timed out after {timeout} seconds.")
        return 124
    except subprocess.CalledProcessError as error:
        print(f"GarminDB sync failed with exit code {error.returncode}.")
        return error.returncode or 1

    print("GarminDB latest sync completed successfully.")
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="Run safe GarminDB latest sync.")
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Sync timeout in seconds. Use 0 or less for no timeout. Default: 1800.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    return run_garmindb_sync(timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
