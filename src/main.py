import os

import requests
from dotenv import load_dotenv

from baseline import calculate_baseline
from decision_engine import make_training_decision
from daily_report import format_daily_report
from garmin_health import load_garmin_health_rows, load_latest_garmin_health_with_source
from gpt_analysis import analyze_recovery
from recovery_rules import calculate_recovery
from strava import fetch_latest_activity
from trend_analysis import analyze_recent_trends
from user_profile import load_user_profile
from weekly_planner import generate_weekly_plan
from weekly_report import format_weekly_report


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
    garmin_rows = load_garmin_health_rows(garmin_source["path"])
    baseline = calculate_baseline(garmin_rows)
    user_profile = load_user_profile()
    recovery = calculate_recovery(garmin_health, baseline=baseline)
    trends = analyze_recent_trends(garmin_source["path"])
    strava_activity = fetch_strava_activity_if_available()
    decision = make_training_decision(
        recovery_result=recovery,
        trend_result=trends,
        garmin_health=garmin_health,
        strava_activity=strava_activity,
        user_profile=user_profile,
    )
    weekly_plan = generate_weekly_plan(
        recovery_result=recovery,
        trend_result=trends,
        user_profile=user_profile,
    )
    analysis = None

    print("Garmin data source:")
    print(f"type: {garmin_source.get('source')}")
    print(f"path: {garmin_source.get('path')}")
    if garmin_source.get("message"):
        print(f"notice: {garmin_source.get('message')}")

    if os.getenv("OPENAI_API_KEY"):
        try:
            analysis = analyze_recovery(
                garmin_health=garmin_health,
                recovery_result=recovery,
                strava_activity=strava_activity,
            )
        except Exception as error:
            print(f"GPT skipped: {error}")
            analysis = None
    else:
        print("GPT skipped: Missing OPENAI_API_KEY environment variable.")

    report = format_daily_report(
        garmin_health=garmin_health,
        recovery_result=recovery,
        strava_activity=strava_activity,
        gpt_analysis=analysis,
        trend_analysis=trends,
        training_decision=decision,
        baseline=baseline,
    )
    print(f"\n{report}")
    print(f"\n{format_weekly_report(weekly_plan)}")


if __name__ == "__main__":
    main()
