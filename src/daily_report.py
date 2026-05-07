def _format_strava_activity(strava_activity):
    if not strava_activity:
        return "無 Strava 補充活動"

    distance_km = float(strava_activity.get("distance") or 0) / 1000
    moving_minutes = int(strava_activity.get("moving_time") or 0) / 60

    return (
        f"活動名稱：{strava_activity.get('name')}\n"
        f"距離：{distance_km:.2f} 公里\n"
        f"移動時間：{moving_minutes:.1f} 分鐘"
    )


def _format_optional_stress(garmin_health):
    stress = garmin_health.get("stress")
    if stress in (None, ""):
        return ""
    return f"壓力：{stress}\n"


def _fallback_recommendation(recovery_level):
    recommendations = {
        "good": "可正常訓練。",
        "moderate": "建議安排中等強度或技術訓練。",
        "poor": "建議休息、恢復，或只做低強度活動。",
    }
    return recommendations.get(recovery_level, "建議保守安排訓練，並觀察身體狀態。")


def format_daily_report(
    garmin_health,
    recovery_result,
    strava_activity=None,
    gpt_analysis=None,
    trend_analysis=None,
    training_decision=None,
    training_load=None,
):
    recovery_level = recovery_result.get("recovery_level")
    recommendation = gpt_analysis or _fallback_recommendation(recovery_level)
    trend_section = _format_trend_analysis(trend_analysis)
    decision_section = _format_training_decision(training_decision)
    training_load_section = _format_training_load(training_load)

    return (
        "Daily Recovery Report\n"
        "=====================\n\n"
        f"日期：{garmin_health.get('date')}\n\n"
        f"Recovery Score：{recovery_result.get('recovery_score')}\n"
        f"Recovery Level：{recovery_level}\n\n"
        "Garmin 指標摘要\n"
        "--------------\n"
        f"睡眠時數：{garmin_health.get('sleep_hours')} 小時\n"
        f"HRV 狀態：{garmin_health.get('hrv_status')}\n"
        f"Body Battery：{garmin_health.get('body_battery')}\n"
        f"靜息心率：{garmin_health.get('resting_hr')}\n"
        f"{_format_optional_stress(garmin_health)}\n"
        "最近 7 天趨勢\n"
        "--------------\n"
        f"{trend_section}\n\n"
        "今日訓練決策\n"
        "--------------\n"
        f"{decision_section}\n\n"
        "Training Load\n"
        "--------------\n"
        f"{training_load_section}\n\n"
        "Strava 補充活動\n"
        "--------------\n"
        f"{_format_strava_activity(strava_activity)}\n\n"
        "今日建議\n"
        "--------\n"
        f"{recommendation}"
    )


def _format_trend_analysis(trend_analysis):
    if not trend_analysis:
        return "無趨勢資料"

    return (
        f"{trend_analysis.get('trend_summary')}\n"
        f"Fatigue Trend：{trend_analysis.get('fatigue_trend')}\n"
        f"Recovery Trend：{trend_analysis.get('recovery_trend')}"
    )


def _format_training_decision(training_decision):
    if not training_decision:
        return "無訓練決策資料"

    return (
        f"Decision：{training_decision.get('decision')}\n"
        f"Intensity：{training_decision.get('intensity')}\n"
        f"Suggested Activity：{training_decision.get('suggested_activity')}\n"
        f"Reason：{training_decision.get('reason')}"
    )


def _format_training_load(training_load):
    if not training_load:
        return "無 Strava training load 資料"

    return (
        f"Last 7 Days Total Minutes：{training_load.get('last_7_days_total_minutes')}\n"
        f"Last 3 Days Total Minutes：{training_load.get('last_3_days_total_minutes')}\n"
        f"Activity Count 7 Days：{training_load.get('activity_count_7_days')}\n"
        f"Training Load Level：{training_load.get('training_load_level')}\n"
        f"Overreaching Risk：{training_load.get('overreaching_risk')}"
    )
