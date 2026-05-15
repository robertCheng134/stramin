import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta


DEFAULT_DB_DIR = "~/HealthData/DBs"
DEFAULT_START_TIME = "09:00"
DEFAULT_CUTOFF_TIME = "11:00"
DEFAULT_RETRY_INTERVAL_MINUTES = 5


def _parse_clock(value):
    return datetime.strptime(value, "%H:%M").time()


def _seconds_until(target_datetime, now):
    return max(0, int((target_datetime - now).total_seconds()))


def _next_start_datetime(now, start_time):
    today_start = datetime.combine(now.date(), start_time, tzinfo=now.tzinfo)
    if now < today_start:
        return today_start
    return today_start + timedelta(days=1)


def _pipeline_command(
    db_dir,
    start_time,
    cutoff_time,
    retry_interval_minutes,
    dry_run,
    sync_garmin=True,
):
    command = [
        sys.executable,
        "automation/run_daily_pipeline.py",
        "--db-dir",
        db_dir,
        "--daily-report-time",
        start_time,
        "--cutoff-time",
        cutoff_time,
        "--retry-interval-minutes",
        str(retry_interval_minutes),
    ]
    if sync_garmin:
        command.insert(2, "--sync-garmin")
    if dry_run:
        command.append("--dry-run")
    return command


def _run_pipeline(command, runner):
    print("Running Stramin daily pipeline...")
    print("Command: " + " ".join(command))
    result = runner(command, check=False, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    return result


def _sleep_until_next_start(now, start_time, sleep_fn):
    next_start = _next_start_datetime(now, start_time)
    seconds = _seconds_until(next_start, now)
    print(f"Morning window complete. Sleeping until {next_start.isoformat()}.")
    sleep_fn(seconds)


def run_scheduler(
    db_dir=DEFAULT_DB_DIR,
    start_time=DEFAULT_START_TIME,
    cutoff_time=DEFAULT_CUTOFF_TIME,
    retry_interval_minutes=DEFAULT_RETRY_INTERVAL_MINUTES,
    dry_run=False,
    now_fn=None,
    sleep_fn=time.sleep,
    runner=subprocess.run,
    max_cycles=None,
):
    now_fn = now_fn or (lambda: datetime.now().astimezone())
    start = _parse_clock(start_time)
    cutoff = _parse_clock(cutoff_time)
    cycles = 0

    while True:
        if max_cycles is not None and cycles >= max_cycles:
            return 0
        cycles += 1

        now = now_fn()
        today_start = datetime.combine(now.date(), start, tzinfo=now.tzinfo)
        today_cutoff = datetime.combine(now.date(), cutoff, tzinfo=now.tzinfo)

        if now < today_start:
            seconds = _seconds_until(today_start, now)
            print(f"Before delivery window. Sleeping until {today_start.isoformat()}.")
            sleep_fn(seconds)
            continue

        if now > today_cutoff:
            print("Morning window has passed; sleeping until next start time.")
            _sleep_until_next_start(now, start, sleep_fn)
            continue

        command = _pipeline_command(
            db_dir,
            start_time,
            cutoff_time,
            retry_interval_minutes,
            dry_run,
            sync_garmin=True,
        )
        result = _run_pipeline(command, runner)

        if result.returncode == 0:
            print("Daily report completed or already sent; stopping retries for today.")
            _sleep_until_next_start(now_fn(), start, sleep_fn)
            continue

        if result.returncode == 2 and now_fn() < today_cutoff:
            retry_seconds = retry_interval_minutes * 60
            print(
                "Pipeline retryable before cutoff. "
                f"Sleeping {retry_interval_minutes} minutes."
            )
            sleep_fn(retry_seconds)
            continue

        print("Pipeline stopped for today; cutoff reached or non-retryable failure.")
        _sleep_until_next_start(now_fn(), start, sleep_fn)


def parse_args():
    parser = argparse.ArgumentParser(description="Run Stramin morning scheduler.")
    parser.add_argument("--db-dir", default=DEFAULT_DB_DIR)
    parser.add_argument("--start-time", default=DEFAULT_START_TIME)
    parser.add_argument("--cutoff-time", default=DEFAULT_CUTOFF_TIME)
    parser.add_argument(
        "--retry-interval-minutes",
        type=int,
        default=DEFAULT_RETRY_INTERVAL_MINUTES,
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    return run_scheduler(
        db_dir=args.db_dir,
        start_time=args.start_time,
        cutoff_time=args.cutoff_time,
        retry_interval_minutes=args.retry_interval_minutes,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
