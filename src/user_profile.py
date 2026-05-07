import json
from pathlib import Path


DEFAULT_USER_PROFILE = {
    "preferred_activities": ["weight_training", "walking", "cycling"],
    "disliked_activities": ["hiit"],
    "training_goal": "general_fitness",
    "available_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    "max_training_days_per_week": 4,
    "weekly_training_minutes_baseline": 240,
    "high_load_multiplier": 1.3,
    "overreaching_3day_minutes_threshold": 180,
    "training_load_sensitivity": "moderate",
}

DEFAULT_PROFILE_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "user_profile.json"
)


def load_user_profile(profile_path=DEFAULT_PROFILE_PATH):
    path = Path(profile_path)
    if not path.exists():
        return DEFAULT_USER_PROFILE.copy()

    with path.open(encoding="utf-8") as profile_file:
        loaded_profile = json.load(profile_file)

    profile = DEFAULT_USER_PROFILE.copy()
    profile.update({key: value for key, value in loaded_profile.items() if value})

    profile["preferred_activities"] = list(profile.get("preferred_activities") or [])
    profile["disliked_activities"] = list(profile.get("disliked_activities") or [])
    profile["available_days"] = list(profile.get("available_days") or [])
    profile["training_goal"] = profile.get("training_goal") or "general_fitness"
    profile["max_training_days_per_week"] = int(
        profile.get("max_training_days_per_week") or 4
    )
    profile["weekly_training_minutes_baseline"] = float(
        profile.get("weekly_training_minutes_baseline") or 240
    )
    profile["high_load_multiplier"] = float(
        profile.get("high_load_multiplier") or 1.3
    )
    profile["overreaching_3day_minutes_threshold"] = float(
        profile.get("overreaching_3day_minutes_threshold") or 180
    )
    profile["training_load_sensitivity"] = (
        profile.get("training_load_sensitivity") or "moderate"
    )

    return profile
