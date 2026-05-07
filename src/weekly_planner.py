DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
RECOVERY_ACTIVITIES = ["walking", "cycling", "mobility", "stretching", "yoga"]
TRAINING_ACTIVITIES = ["weight_training", "cycling", "running", "walking"]
INTENSITY_DOWNGRADE = {
    "high": "moderate",
    "moderate": "low",
    "low": "very low",
    "very low": "very low",
    "none": "none",
}


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


def _planned_workout_for(day, user_profile):
    planned_workouts = user_profile.get("planned_workouts") or {}
    planned_workout = planned_workouts.get(day)
    if planned_workout:
        return {
            "activity": planned_workout.get("activity", "rest"),
            "intensity": planned_workout.get("intensity", "moderate"),
            "focus": planned_workout.get("focus"),
        }

    weekly_structure = user_profile.get("weekly_structure") or {}
    activity = weekly_structure.get(day, "rest")
    return {
        "activity": activity,
        "intensity": "none" if activity == "rest" else "moderate",
        "focus": None,
    }


def _downgrade_intensity(intensity):
    return INTENSITY_DOWNGRADE.get(intensity, "low")


def adjust_training_plan(
    planned_workout,
    recovery_result,
    trend_result,
    training_load=None,
):
    planned_activity = planned_workout.get("activity", "rest")
    original_intensity = planned_workout.get("intensity", "moderate")
    recovery_level = recovery_result.get("recovery_level")
    fatigue_trend = (trend_result or {}).get("fatigue_trend", "stable")
    overreaching_risk = (training_load or {}).get("overreaching_risk", False)

    if planned_activity == "rest":
        return {
            "planned_activity": planned_activity,
            "adjusted_activity": "rest",
            "original_intensity": "none",
            "adjusted_intensity": "none",
            "adaptation_reason": "Planned rest day; no heavy training scheduled.",
        }

    if recovery_level == "poor" and planned_activity not in RECOVERY_ACTIVITIES:
        return {
            "planned_activity": planned_activity,
            "adjusted_activity": "walking",
            "original_intensity": original_intensity,
            "adjusted_intensity": "very low",
            "adaptation_reason": "Poor recovery; planned training changed to recovery walk.",
        }

    if recovery_level == "poor":
        return {
            "planned_activity": planned_activity,
            "adjusted_activity": planned_activity,
            "original_intensity": original_intensity,
            "adjusted_intensity": "very low",
            "adaptation_reason": "Poor recovery; intensity reduced for a recovery-focused session.",
        }

    if fatigue_trend == "worsening":
        return {
            "planned_activity": planned_activity,
            "adjusted_activity": "walking",
            "original_intensity": original_intensity,
            "adjusted_intensity": "very low",
            "adaptation_reason": "Fatigue is worsening; added a recovery session.",
        }

    if overreaching_risk and original_intensity in {"moderate", "high"}:
        return {
            "planned_activity": planned_activity,
            "adjusted_activity": planned_activity,
            "original_intensity": original_intensity,
            "adjusted_intensity": _downgrade_intensity(original_intensity),
            "adaptation_reason": "Overreaching risk detected; intensity reduced by one level.",
        }

    return {
        "planned_activity": planned_activity,
        "adjusted_activity": planned_activity,
        "original_intensity": original_intensity,
        "adjusted_intensity": original_intensity,
        "adaptation_reason": "Plan kept as scheduled.",
    }


def generate_weekly_plan(recovery_result, trend_result, user_profile, training_load=None):
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
    fallback_intensity = _intensity_for(recovery_level, fatigue_trend)
    fallback_reason = _reason_for(recovery_level, fatigue_trend, training_goal)

    weekly_plan = []
    for day in DAYS:
        planned_workout = _planned_workout_for(day, user_profile)
        planned_activity = planned_workout["activity"]
        is_planned_rest = planned_activity == "rest" or day in rest_days
        can_train = (
            day in available_days
            and not is_planned_rest
            and training_days_used < training_capacity
        )

        if can_train:
            adapted_plan = adjust_training_plan(
                planned_workout,
                recovery_result,
                trend_result,
                training_load,
            )
            weekly_plan.append(
                {
                    "day": day,
                    **adapted_plan,
                    "activity": adapted_plan["adjusted_activity"],
                    "intensity": adapted_plan["adjusted_intensity"],
                    "reason": adapted_plan["adaptation_reason"],
                }
            )
            training_days_used += 1
        else:
            original_intensity = "none" if is_planned_rest else planned_workout["intensity"]
            adaptation_reason = (
                "Planned rest day; no heavy training scheduled."
                if is_planned_rest
                else "Rest day to preserve recovery and stay within weekly training limits."
            )
            weekly_plan.append(
                {
                    "day": day,
                    "planned_activity": planned_activity,
                    "adjusted_activity": "rest",
                    "original_intensity": original_intensity,
                    "adjusted_intensity": "none",
                    "adaptation_reason": adaptation_reason,
                    "activity": "rest",
                    "intensity": "none",
                    "reason": adaptation_reason,
                }
            )

    return weekly_plan
