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


def _adjust_planned_activity(planned_activity, recovery_level, fatigue_trend, user_profile):
    disliked = set(user_profile.get("disliked_activities") or [])

    if planned_activity in disliked:
        return _select_activity(user_profile, RECOVERY_ACTIVITIES)

    if planned_activity == "rest":
        return "rest"

    if recovery_level == "poor":
        return _select_activity(user_profile, RECOVERY_ACTIVITIES)

    if fatigue_trend == "worsening" and planned_activity not in RECOVERY_ACTIVITIES:
        return _select_activity(user_profile, RECOVERY_ACTIVITIES)

    return planned_activity


def _planned_activity_for(day, user_profile):
    weekly_structure = user_profile.get("weekly_structure") or {}
    return weekly_structure.get(day, "rest")


def generate_weekly_plan(recovery_result, trend_result, user_profile):
    recovery_level = recovery_result.get("recovery_level")
    fatigue_trend = (trend_result or {}).get("fatigue_trend", "stable")
    available_days = set(user_profile.get("available_days") or DAYS)
    training_goal = user_profile.get("training_goal", "general_fitness")
    max_training_days = int(user_profile.get("max_training_days_per_week") or 4)
    rest_days = set(user_profile.get("rest_days") or [])

    training_capacity = _training_capacity(
        recovery_level,
        fatigue_trend,
        max_training_days,
    )
    training_days_used = 0
    intensity = _intensity_for(recovery_level, fatigue_trend)
    reason = _reason_for(recovery_level, fatigue_trend, training_goal)

    weekly_plan = []
    for day in DAYS:
        planned_activity = _planned_activity_for(day, user_profile)
        is_planned_rest = planned_activity == "rest" or day in rest_days
        can_train = (
            day in available_days
            and not is_planned_rest
            and training_days_used < training_capacity
        )

        if can_train:
            adjusted_activity = _adjust_planned_activity(
                planned_activity,
                recovery_level,
                fatigue_trend,
                user_profile,
            )
            weekly_plan.append(
                {
                    "day": day,
                    "planned_activity": planned_activity,
                    "adjusted_activity": adjusted_activity,
                    "activity": adjusted_activity,
                    "intensity": intensity,
                    "reason": reason,
                }
            )
            training_days_used += 1
        else:
            weekly_plan.append(
                {
                    "day": day,
                    "planned_activity": planned_activity,
                    "adjusted_activity": "rest",
                    "activity": "rest",
                    "intensity": "none",
                    "reason": "Rest day to preserve recovery and stay within weekly training limits.",
                }
            )

    return weekly_plan
