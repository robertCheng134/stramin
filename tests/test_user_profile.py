import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from user_profile import load_user_profile


def test_user_profile_includes_device_start_dates_by_default(tmp_path):
    profile_path = tmp_path / "user_profile.json"
    profile_path.write_text(
        json.dumps({"preferred_activities": ["walking"]}),
        encoding="utf-8",
    )

    profile = load_user_profile(profile_path)

    assert profile["garmin_start_date"] == ""
    assert profile["apple_watch_start_date"] == ""
    assert profile["samsung_health_start_date"] == ""


def test_user_profile_loads_device_start_dates(tmp_path):
    profile_path = tmp_path / "user_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "garmin_start_date": "2026-05-01",
                "apple_watch_start_date": "2026-04-01",
                "samsung_health_start_date": "2026-03-01",
            }
        ),
        encoding="utf-8",
    )

    profile = load_user_profile(profile_path)

    assert profile["garmin_start_date"] == "2026-05-01"
    assert profile["apple_watch_start_date"] == "2026-04-01"
    assert profile["samsung_health_start_date"] == "2026-03-01"
