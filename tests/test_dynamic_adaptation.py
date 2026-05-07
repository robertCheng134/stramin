import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from weekly_planner import adjust_training_plan, generate_weekly_plan


def test_poor_recovery_cancels_high_intensity():
    adapted = adjust_training_plan(
        {"activity": "weight_training", "intensity": "high"},
        {"recovery_level": "poor"},
        {"fatigue_trend": "stable"},
        training_load=None,
    )

    assert adapted["adjusted_activity"] in {"walking", "rest"}
    assert adapted["adjusted_intensity"] != "high"


def test_overreaching_risk_lowers_intensity():
    adapted = adjust_training_plan(
        {"activity": "cycling", "intensity": "moderate"},
        {"recovery_level": "good"},
        {"fatigue_trend": "stable"},
        training_load={"overreaching_risk": True},
    )

    assert adapted["adjusted_activity"] == "cycling"
    assert adapted["adjusted_intensity"] == "low"


def test_rest_day_does_not_schedule_heavy_training():
    profile = {
        "preferred_activities": ["weight_training", "walking"],
        "disliked_activities": [],
        "available_days": ["Monday", "Tuesday", "Wednesday"],
        "max_training_days_per_week": 3,
        "weekly_structure": {"Monday": "weight_training", "Sunday": "rest"},
        "planned_workouts": {
            "Sunday": {"activity": "weight_training", "intensity": "high"}
        },
        "rest_days": ["Sunday"],
        "training_goal": "general_fitness",
    }

    plan = generate_weekly_plan(
        {"recovery_level": "good"},
        {"fatigue_trend": "stable"},
        profile,
    )

    sunday = plan[6]
    assert sunday["adjusted_activity"] == "rest"
    assert sunday["adjusted_intensity"] == "none"
