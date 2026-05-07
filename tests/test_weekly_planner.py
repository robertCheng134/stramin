import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from weekly_planner import generate_weekly_plan


def _profile():
    return {
        "preferred_activities": ["weight_training", "walking", "cycling"],
        "disliked_activities": ["hiit"],
        "training_goal": "general_fitness",
        "available_days": [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ],
        "max_training_days_per_week": 6,
        "weekly_structure": {
            "Monday": "weight_training",
            "Tuesday": "walking",
            "Wednesday": "rest",
            "Thursday": "weight_training",
            "Friday": "cycling",
            "Saturday": "weight_training",
            "Sunday": "rest",
        },
        "rest_days": ["Sunday"],
    }


def test_weekly_structure_is_used():
    plan = generate_weekly_plan(
        {"recovery_level": "good"},
        {"fatigue_trend": "stable"},
        _profile(),
    )

    monday = plan[0]
    assert monday["planned_activity"] == "weight_training"
    assert monday["adjusted_activity"] == "weight_training"


def test_poor_recovery_adjusts_activity_down():
    plan = generate_weekly_plan(
        {"recovery_level": "poor"},
        {"fatigue_trend": "stable"},
        _profile(),
    )

    monday = plan[0]
    assert monday["planned_activity"] == "weight_training"
    assert monday["adjusted_activity"] == "walking"
    assert monday["intensity"] == "very low"


def test_rest_days_do_not_schedule_training():
    plan = generate_weekly_plan(
        {"recovery_level": "good"},
        {"fatigue_trend": "stable"},
        _profile(),
    )

    sunday = plan[6]
    assert sunday["planned_activity"] == "rest"
    assert sunday["adjusted_activity"] == "rest"
    assert sunday["intensity"] == "none"
