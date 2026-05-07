import json
from pathlib import Path


DEFAULT_USER_PROFILE = {
    "preferred_activities": ["weight_training", "walking", "cycling"],
    "disliked_activities": ["hiit"],
    "training_goal": "general_fitness",
    "available_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    "max_training_days_per_week": 4,
    "weekly_structure": {
        "Monday": "weight_training",
        "Tuesday": "walking",
        "Wednesday": "rest",
        "Thursday": "weight_training",
        "Friday": "cycling",
        "Saturday": "weight_training",
        "Sunday": "rest",
    },
    "priority_muscle_groups": ["chest", "back", "legs"],
    "preferred_training_time": "evening",
    "rest_days": ["Sunday"],
    "session_duration_minutes": 60,
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
    profile["priority_muscle_groups"] = list(
        profile.get("priority_muscle_groups") or []
    )
    profile["rest_days"] = list(profile.get("rest_days") or [])
    profile["weekly_structure"] = dict(profile.get("weekly_structure") or {})
    profile["training_goal"] = profile.get("training_goal") or "general_fitness"
    profile["preferred_training_time"] = (
        profile.get("preferred_training_time") or "evening"
    )
    profile["max_training_days_per_week"] = int(
        profile.get("max_training_days_per_week") or 4
    )
    profile["session_duration_minutes"] = int(
        profile.get("session_duration_minutes") or 60
    )

    return profile
