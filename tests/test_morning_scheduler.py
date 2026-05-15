import importlib.util
import sys
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
SCHEDULER_PATH = ROOT_DIR / "automation" / "run_morning_scheduler.py"


def _load_scheduler_module():
    spec = importlib.util.spec_from_file_location("run_morning_scheduler", SCHEDULER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scheduler_module = _load_scheduler_module()


class FakeResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _now_sequence(*values):
    remaining = list(values)

    def now_fn():
        if len(remaining) > 1:
            return remaining.pop(0)
        return remaining[0]

    return now_fn


def _dt(value):
    return datetime.fromisoformat(value)


def test_scheduler_before_start_time_does_not_run_pipeline_immediately():
    calls = []
    sleeps = []

    scheduler_module.run_scheduler(
        now_fn=_now_sequence(_dt("2026-05-12T08:30:00+08:00")),
        sleep_fn=sleeps.append,
        runner=lambda *args, **kwargs: calls.append((args, kwargs)),
        max_cycles=1,
    )

    assert calls == []
    assert sleeps == [1800]


def test_scheduler_within_window_runs_pipeline():
    calls = []
    sleeps = []

    def runner(command, **kwargs):
        calls.append({"command": command, "kwargs": kwargs})
        return FakeResult(0, "Daily pipeline ready: telegram_sent=true")

    scheduler_module.run_scheduler(
        db_dir="/tmp/DBs",
        now_fn=_now_sequence(
            _dt("2026-05-12T09:05:00+08:00"),
            _dt("2026-05-12T09:06:00+08:00"),
        ),
        sleep_fn=sleeps.append,
        runner=runner,
        max_cycles=1,
    )

    assert len(calls) == 1
    assert calls[0]["command"][:4] == [
        sys.executable,
        "automation/run_daily_pipeline.py",
        "--sync-garmin",
        "--db-dir",
    ]
    assert "--sync-garmin" in calls[0]["command"]
    assert calls[0]["command"][0] != "python3"
    assert "/tmp/DBs" in calls[0]["command"]
    assert calls[0]["command"][calls[0]["command"].index("--db-dir") + 1] == (
        "/tmp/DBs"
    )
    assert calls[0]["kwargs"] == {
        "check": False,
        "capture_output": True,
        "text": True,
    }
    assert sleeps


def test_scheduler_already_sent_noop_stops_retrying_for_the_day():
    calls = []
    sleeps = []

    def runner(command, **kwargs):
        calls.append(command)
        return FakeResult(0, "Daily pipeline no-op: report already sent for today")

    scheduler_module.run_scheduler(
        now_fn=_now_sequence(
            _dt("2026-05-12T09:10:00+08:00"),
            _dt("2026-05-12T09:11:00+08:00"),
        ),
        sleep_fn=sleeps.append,
        runner=runner,
        max_cycles=1,
    )

    assert len(calls) == 1
    assert calls[0][0] == sys.executable
    assert sleeps and sleeps[0] > 20 * 60 * 60


def test_scheduler_successful_send_stops_retrying_for_the_day():
    calls = []
    sleeps = []

    def runner(command, **kwargs):
        calls.append(command)
        return FakeResult(0, "Daily pipeline ready: telegram_sent=true")

    scheduler_module.run_scheduler(
        now_fn=_now_sequence(
            _dt("2026-05-12T09:15:00+08:00"),
            _dt("2026-05-12T09:16:00+08:00"),
        ),
        sleep_fn=sleeps.append,
        runner=runner,
        max_cycles=1,
    )

    assert len(calls) == 1
    assert calls[0][0] == sys.executable
    assert sleeps and sleeps[0] > 20 * 60 * 60


def test_scheduler_retryable_failure_retries_after_interval():
    calls = []
    sleeps = []

    def runner(command, **kwargs):
        calls.append(command)
        return FakeResult(2, "Daily pipeline retryable")

    scheduler_module.run_scheduler(
        retry_interval_minutes=5,
        now_fn=_now_sequence(
            _dt("2026-05-12T09:20:00+08:00"),
            _dt("2026-05-12T09:21:00+08:00"),
            _dt("2026-05-12T09:26:00+08:00"),
            _dt("2026-05-12T09:27:00+08:00"),
        ),
        sleep_fn=sleeps.append,
        runner=runner,
        max_cycles=2,
    )

    assert len(calls) == 2
    assert calls[0][0] == sys.executable
    assert calls[1][0] == sys.executable
    assert sleeps[0] == 300


def test_scheduler_after_cutoff_does_not_run_pipeline_and_sleeps_until_next_start(
    capsys,
):
    calls = []
    sleeps = []

    def runner(command, **kwargs):
        calls.append(command)
        return FakeResult(2, "Daily pipeline retryable")

    scheduler_module.run_scheduler(
        now_fn=_now_sequence(
            _dt("2026-05-12T11:30:00+08:00"),
            _dt("2026-05-12T11:31:00+08:00"),
        ),
        sleep_fn=sleeps.append,
        runner=runner,
        max_cycles=1,
    )

    assert calls == []
    assert sleeps and sleeps[0] > 21 * 60 * 60
    assert (
        "Morning window has passed; sleeping until next start time."
        in capsys.readouterr().out
    )


def test_scheduler_dry_run_passes_dry_run_to_pipeline():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return FakeResult(0, "Daily pipeline ready: telegram_sent=false")

    scheduler_module.run_scheduler(
        dry_run=True,
        now_fn=_now_sequence(
            _dt("2026-05-12T09:05:00+08:00"),
            _dt("2026-05-12T09:06:00+08:00"),
        ),
        sleep_fn=lambda seconds: None,
        runner=runner,
        max_cycles=1,
    )

    assert "--dry-run" in calls[0]
    assert calls[0][0] == sys.executable


def test_pipeline_command_uses_current_interpreter_not_hardcoded_python3():
    command = scheduler_module._pipeline_command(
        db_dir="/tmp/DBs",
        start_time="09:00",
        cutoff_time="11:00",
        retry_interval_minutes=5,
        dry_run=False,
    )

    assert command[0] == sys.executable
    assert command[0] != "python3"


def test_pipeline_command_includes_sync_garmin_by_default():
    command = scheduler_module._pipeline_command(
        db_dir="/tmp/DBs",
        start_time="09:00",
        cutoff_time="11:00",
        retry_interval_minutes=5,
        dry_run=False,
    )

    assert command[:4] == [
        sys.executable,
        "automation/run_daily_pipeline.py",
        "--sync-garmin",
        "--db-dir",
    ]
    assert command[command.index("--db-dir") + 1] == "/tmp/DBs"

