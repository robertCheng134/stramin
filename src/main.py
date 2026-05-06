import os

import requests
from dotenv import load_dotenv

from daily_report import format_daily_report
from garmin_health import load_latest_garmin_health_with_source
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

    garmin_health, garmin_source = load_latest_garmin_health_with_source()
    recovery = calculate_recovery(garmin_health)
    strava_activity = fetch_strava_activity_if_available()
    analysis = None

    print("Garmin data source:")
    print(f"type: {garmin_source.get('source')}")
    print(f"path: {garmin_source.get('path')}")
    if garmin_source.get("message"):
        print(f"notice: {garmin_source.get('message')}")

    if os.getenv("OPENAI_API_KEY"):
        analysis = analyze_recovery(
            garmin_health=garmin_health,
            recovery_result=recovery,
            strava_activity=strava_activity,
        )
    else:
        print("\nGPT skipped: Missing OPENAI_API_KEY environment variable.")

    report = format_daily_report(
        garmin_health=garmin_health,
        recovery_result=recovery,
        strava_activity=strava_activity,
        gpt_analysis=analysis,
    )
    print(f"\n{report}")


if __name__ == "__main__":
    main()
