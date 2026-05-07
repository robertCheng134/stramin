import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from training_load import analyze_training_load


def _activities_with_minutes(minutes):
    return [{"name": "Ride", "distance": 10000, "moving_time": minutes * 60}]


def test_baseline_240_keeps_250_minutes_moderate():
    training_load = analyze_training_load(
        _activities_with_minutes(250),
        user_profile={
            "weekly_training_minutes_baseline": 240,
            "high_load_multiplier": 1.3,
            "overreaching_3day_minutes_threshold": 300,
            "training_load_sensitivity": "moderate",
        },
    )

    assert training_load["training_load_level"] == "moderate"


def test_baseline_120_makes_250_minutes_high():
    training_load = analyze_training_load(
        _activities_with_minutes(250),
        user_profile={
            "weekly_training_minutes_baseline": 120,
            "high_load_multiplier": 1.3,
            "overreaching_3day_minutes_threshold": 300,
            "training_load_sensitivity": "moderate",
        },
    )

    assert training_load["training_load_level"] == "high"
