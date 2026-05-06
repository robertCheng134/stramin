import os

from dotenv import load_dotenv
from openai import OpenAI


def _format_strava_activity(strava_activity):
    if not strava_activity:
        return "沒有提供 Strava 活動資料。"

    distance_km = (float(strava_activity.get("distance") or 0) / 1000)
    moving_minutes = (int(strava_activity.get("moving_time") or 0) / 60)

    return (
        f"- 活動名稱：{strava_activity.get('name')}\n"
        f"- 距離：{distance_km:.2f} 公里\n"
        f"- 移動時間：{moving_minutes:.1f} 分鐘"
    )


def _format_optional_stress(garmin_health):
    stress = garmin_health.get("stress")
    if stress in (None, ""):
        return "- 壓力：未提供\n"
    return f"- 壓力：{stress}\n"


def analyze_recovery(garmin_health, recovery_result, strava_activity=None):
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一位專業跑步與耐力訓練教練，擅長根據 Garmin 健康指標判斷恢復狀態。"
                    "Garmin 身體狀態是主要依據，Strava 活動資料只能當作補充背景。"
                    "recovery_score 和 recovery_level 是已經由規則系統計算好的結果，你不能重新計算或更改分數。"
                    "如果 recovery_level 是 poor，必須優先建議恢復、低強度活動或休息。"
                    "請用繁體中文，給出簡潔、實用、可執行的分析。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "請根據以下 Garmin 健康資料做今日訓練判斷：\n"
                    f"- 日期：{garmin_health.get('date')}\n"
                    f"- 睡眠時數：{garmin_health.get('sleep_hours')} 小時\n"
                    f"- HRV 狀態：{garmin_health.get('hrv_status')}\n"
                    f"- Body Battery：{garmin_health.get('body_battery')}\n"
                    f"- 靜息心率：{garmin_health.get('resting_hr')}\n"
                    f"{_format_optional_stress(garmin_health)}\n"
                    "規則系統恢復結果：\n"
                    f"- recovery_score：{recovery_result.get('recovery_score')}\n"
                    f"- recovery_level：{recovery_result.get('recovery_level')}\n"
                    "請只根據這個既有分數與等級做解釋，不要重新計算 recovery_score。\n\n"
                    "Strava 最新活動補充資料：\n"
                    f"{_format_strava_activity(strava_activity)}\n\n"
                    "請嚴格輸出以下四段：\n"
                    "1. 今日恢復狀態\n"
                    "2. 是否適合訓練\n"
                    "3. 建議訓練強度\n"
                    "4. 明日建議"
                ),
            },
        ],
        temperature=0.7,
    )

    return response.choices[0].message.content
