DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
RECOVERY_ACTIVITIES = ["walking", "cycling", "mobility", "stretching", "yoga"]
TRAINING_ACTIVITIES = ["weight_training", "cycling", "running", "walking"]


def _select_activity(user_profile, candidates):
    disliked = set(user_profile.get("disliked_activities") or [])
    preferred = [
        activity
        for activity in user_profile.get("preferred_activities", [])
        if activity not in disliked
    ]

    if preferred:
        for activity in preferred:
            if activity in candidates:
                return activity

    for activity in candidates:
        if activity not in disliked:
            return activity

    return "rest"


def _training_capacity(recovery_level, fatigue_trend, max_training_days):
    if recovery_level == "poor":
        return min(max_training_days, 2)
    if fatigue_trend == "worsening":
        return min(max_training_days, 3)
    if recovery_level == "good":
        return max_training_days
    return min(max_training_days, 4)


def _intensity_for(recovery_level, fatigue_trend):
    if recovery_level == "poor":
        return "very low"
    if fatigue_trend == "worsening":
        return "low"
    if recovery_level == "good":
        return "moderate"
    return "low to moderate"


def _reason_for(recovery_level, fatigue_trend, training_goal):
    if recovery_level == "poor":
        return "Recovery is poor, so the week prioritizes rest and gentle movement."
    if fatigue_trend == "worsening":
        return "Fatigue is worsening, so intensity is reduced for this week."
    if recovery_level == "good":
        return f"Recovery is good, supporting normal training toward {training_goal}."
    return f"Recovery is moderate, so training supports {training_goal} conservatively."


def generate_weekly_plan(recovery_result, trend_result, user_profile):
    recovery_level = recovery_result.get("recovery_level")
    fatigue_trend = (trend_result or {}).get("fatigue_trend", "stable")
    available_days = set(user_profile.get("available_days") or DAYS)
    training_goal = user_profile.get("training_goal", "general_fitness")
    max_training_days = int(user_profile.get("max_training_days_per_week") or 4)
    candidate_activities = (
        RECOVERY_ACTIVITIES
        if recovery_level == "poor" or fatigue_trend == "worsening"
        else TRAINING_ACTIVITIES
    )

    training_capacity = _training_capacity(
        recovery_level,
        fatigue_trend,
        max_training_days,
    )
    training_days_used = 0
    activity = _select_activity(user_profile, candidate_activities)
    intensity = _intensity_for(recovery_level, fatigue_trend)
    reason = _reason_for(recovery_level, fatigue_trend, training_goal)

    weekly_plan = []
    for day in DAYS:
        can_train = day in available_days and training_days_used < training_capacity

        if can_train:
            weekly_plan.append(
                {
                    "day": day,
                    "activity": activity,
                    "intensity": intensity,
                    "reason": reason,
                }
            )
            training_days_used += 1
        else:
            weekly_plan.append(
                {
                    "day": day,
                    "activity": "rest",
                    "intensity": "none",
                    "reason": "Rest day to preserve recovery and stay within weekly training limits.",
                }
            )

    return weekly_plan
