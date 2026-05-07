import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from baseline import calculate_baseline


def _garmin_row(day, resting_hr):
    return {
        "date": f"2026-05-{day:02d}",
        "sleep_hours": "7",
        "body_battery": "70",
        "resting_hr": str(resting_hr),
    }


def test_less_than_7_rows_is_insufficient_data():
    baseline = calculate_baseline([_garmin_row(day, 50) for day in range(1, 7)])

    assert baseline["baseline_status"] == "insufficient_data"


def test_7_or_more_rows_is_ready():
    baseline = calculate_baseline([_garmin_row(day, 50) for day in range(1, 8)])

    assert baseline["baseline_status"] == "ready"


def test_average_resting_hr_is_calculated_correctly():
    baseline = calculate_baseline(
        [
            _garmin_row(1, 50),
            _garmin_row(2, 52),
            _garmin_row(3, 54),
            _garmin_row(4, 56),
            _garmin_row(5, 58),
            _garmin_row(6, 60),
            _garmin_row(7, 62),
        ]
    )

    assert baseline["average_resting_hr"] == 56.0
