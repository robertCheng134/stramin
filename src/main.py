import os

import requests
from dotenv import load_dotenv

from garmin_health import load_latest_garmin_health
from gpt_analysis import analyze_recovery
from recovery_rules import calculate_recovery
from strava import fetch_latest_activity


def fetch_strava_activity_if_available():
    try:
        return fetch_latest_activity()
    except RuntimeError as error:
        print(f"Strava skipped: {error}")
    except requests.RequestException as error:
        print(f"Strava skipped: {error}")

    return None


def main():
    load_dotenv()

    garmin_health = load_latest_garmin_health()
    recovery = calculate_recovery(garmin_health)
    strava_activity = fetch_strava_activity_if_available()

    print("Garmin health:")
    print(f"date: {garmin_health.get('date')}")
    print(f"sleep_hours: {garmin_health.get('sleep_hours')}")
    print(f"hrv_status: {garmin_health.get('hrv_status')}")
    print(f"body_battery: {garmin_health.get('body_battery')}")
    print(f"resting_hr: {garmin_health.get('resting_hr')}")
    print(f"stress: {garmin_health.get('stress')}")

    print("\nRecovery Rules:")
    print(f"Recovery Score: {recovery.get('recovery_score')}")
    print(f"Recovery Level: {recovery.get('recovery_level')}")

    if strava_activity:
        print("\nStrava supplement:")
        print(f"name: {strava_activity.get('name')}")
        print(f"distance: {strava_activity.get('distance')}")
        print(f"moving_time: {strava_activity.get('moving_time')}")

    if not os.getenv("OPENAI_API_KEY"):
        print("\nGPT skipped: Missing OPENAI_API_KEY environment variable.")
        return

    analysis = analyze_recovery(
        garmin_health=garmin_health,
        recovery_result=recovery,
        strava_activity=strava_activity,
    )

    print("\nGPT 中文分析結果:")
    print(analysis)


if __name__ == "__main__":
    main()
