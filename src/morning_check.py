import os
from datetime import date

from dotenv import load_dotenv

from add_garmin_entry import collect_garmin_entry, save_garmin_entry
from daily_report import format_daily_report
from decision_engine import make_training_decision
from garmin_health import GARMIN_HEALTH_CSV_PATH, load_latest_garmin_health
from gpt_analysis import analyze_recovery
from logger import get_logger
from recovery_rules import calculate_recovery
from trend_analysis import analyze_recent_trends
from user_profile import load_user_profile


logger = get_logger(__name__)


def main():
    load_dotenv()

    today = date.today().isoformat()
    print(f"Today's date: {today}")

    entry = collect_garmin_entry(today)
    if not save_garmin_entry(entry):
        return

    garmin_health = load_latest_garmin_health(GARMIN_HEALTH_CSV_PATH)
    user_profile = load_user_profile()
    recovery = calculate_recovery(garmin_health)
    trends = analyze_recent_trends(GARMIN_HEALTH_CSV_PATH)
    decision = make_training_decision(
        recovery_result=recovery,
        trend_result=trends,
        garmin_health=garmin_health,
        strava_activity=None,
        user_profile=user_profile,
    )

    gpt_analysis = None
    if os.getenv("OPENAI_API_KEY"):
        try:
            gpt_analysis = analyze_recovery(
                garmin_health=garmin_health,
                recovery_result=recovery,
                strava_activity=None,
            )
        except Exception as error:
            logger.warning("GPT skipped: %s", error)
    else:
        logger.warning("GPT skipped: Missing OPENAI_API_KEY environment variable.")

    report = format_daily_report(
        garmin_health=garmin_health,
        recovery_result=recovery,
        strava_activity=None,
        gpt_analysis=gpt_analysis,
        trend_analysis=trends,
        training_decision=decision,
    )
    print(f"\n{report}")


if __name__ == "__main__":
    main()
