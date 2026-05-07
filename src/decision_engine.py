REST_ACTIVITIES = ["rest"]
RECOVERY_ACTIVITIES = ["walking", "mobility", "stretching", "easy_cycling", "yoga"]
LIGHT_TRAINING_ACTIVITIES = ["walking", "cycling", "weight_training", "mobility"]
TRAINING_ACTIVITIES = ["weight_training", "cycling", "running", "walking"]


def _select_activity(user_profile, candidates):
    profile = user_profile or {}
    disliked = set(profile.get("disliked_activities") or [])
    preferred = [
        activity
        for activity in profile.get("preferred_activities", [])
        if activity not in disliked
    ]

    for activity in preferred:
        if activity in candidates:
            return activity

    for activity in candidates:
        if activity not in disliked:
            return activity

    return "no_recommended_activity"


def make_training_decision(
    recovery_result,
    trend_result=None,
    garmin_health=None,
    strava_activity=None,
    user_profile=None,
    training_load=None,
):
    recovery_score = int(recovery_result.get("recovery_score") or 0)
    recovery_level = recovery_result.get("recovery_level")
    fatigue_trend = (trend_result or {}).get("fatigue_trend", "stable")
    recovery_trend = (trend_result or {}).get("recovery_trend", "stable")
    load = training_load or {}

    if recovery_level == "poor" and fatigue_trend == "worsening":
        return {
            "decision": "rest",
            "intensity": "none",
            "suggested_activity": _select_activity(user_profile, REST_ACTIVITIES),
            "reason": "恢復等級為 poor，且疲勞趨勢正在惡化，今天應優先休息。",
        }

    if load.get("overreaching_risk"):
        return {
            "decision": "recovery_day",
            "intensity": "very low",
            "suggested_activity": _select_activity(user_profile, RECOVERY_ACTIVITIES),
            "reason": "最近 3 天訓練時間偏高，有 overreaching 風險，建議恢復日。",
        }

    if recovery_score < 40:
        return {
            "decision": "recovery_day",
            "intensity": "very low",
            "suggested_activity": _select_activity(user_profile, RECOVERY_ACTIVITIES),
            "reason": "Recovery Score 低於 40，適合安排恢復日或非常低強度活動。",
        }

    if load.get("training_load_level") == "high":
        return {
            "decision": "light_training",
            "intensity": "low",
            "suggested_activity": _select_activity(user_profile, LIGHT_TRAINING_ACTIVITIES),
            "reason": "最近 7 天訓練負荷偏高，建議降低今日訓練強度。",
        }

    if recovery_level == "moderate" and recovery_trend == "declining":
        return {
            "decision": "light_training",
            "intensity": "low",
            "suggested_activity": _select_activity(user_profile, LIGHT_TRAINING_ACTIVITIES),
            "reason": "恢復等級為 moderate，但恢復趨勢下降，建議降低訓練負荷。",
        }

    if recovery_level == "good" and fatigue_trend != "worsening":
        return {
            "decision": "train",
            "intensity": "normal",
            "suggested_activity": _select_activity(user_profile, TRAINING_ACTIVITIES),
            "reason": "恢復等級為 good，且疲勞趨勢沒有惡化，可以正常訓練。",
        }

    return {
        "decision": "light_training",
        "intensity": "low to moderate",
        "suggested_activity": _select_activity(user_profile, LIGHT_TRAINING_ACTIVITIES),
        "reason": "目前狀態未達完整訓練條件，建議保守安排輕量訓練。",
    }
