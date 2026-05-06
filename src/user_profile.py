import json
from pathlib import Path


DEFAULT_USER_PROFILE = {
    "preferred_activities": ["weight_training", "walking", "cycling"],
    "disliked_activities": ["hiit"],
    "training_goal": "general_fitness",
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
    profile["training_goal"] = profile.get("training_goal") or "general_fitness"

    return profile
