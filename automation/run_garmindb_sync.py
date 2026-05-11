import argparse
import subprocess


SYNC_COMMAND = [
    "garmindb_cli.py",
    "--all",
    "--download",
    "--import",
    "--analyze",
    "--latest",
]
DEFAULT_TIMEOUT_SECONDS = 1800


def build_sync_command():
    return list(SYNC_COMMAND)


def run_garmindb_sync(timeout=DEFAULT_TIMEOUT_SECONDS):
    command = build_sync_command()
    print("Starting GarminDB latest sync...")
    print("Command: " + " ".join(command))

    try:
        subprocess.run(command, timeout=timeout, check=True)
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
        help="Sync timeout in seconds. Default: 1800.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    return run_garmindb_sync(timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
