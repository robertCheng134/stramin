import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from decision_engine import make_training_decision


def test_poor_and_worsening_decides_rest():
    decision = make_training_decision(
        recovery_result={"recovery_score": 30, "recovery_level": "poor"},
        trend_result={"fatigue_trend": "worsening", "recovery_trend": "declining"},
    )

    assert decision["decision"] == "rest"


def test_recovery_score_under_40_decides_recovery_day():
    decision = make_training_decision(
        recovery_result={"recovery_score": 35, "recovery_level": "moderate"},
        trend_result={"fatigue_trend": "stable", "recovery_trend": "stable"},
    )

    assert decision["decision"] == "recovery_day"


def test_disliked_activities_are_not_recommended():
    decision = make_training_decision(
        recovery_result={"recovery_score": 85, "recovery_level": "good"},
        trend_result={"fatigue_trend": "stable", "recovery_trend": "recovering"},
        user_profile={
            "preferred_activities": ["hiit", "cycling"],
            "disliked_activities": ["hiit"],
            "training_goal": "general_fitness",
        },
    )

    assert decision["suggested_activity"] != "hiit"
    assert decision["suggested_activity"] == "cycling"
