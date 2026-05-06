import os

import requests
from dotenv import load_dotenv


STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"


def fetch_latest_activity():
    load_dotenv()

    access_token = os.getenv("STRAVA_ACCESS_TOKEN")
    if not access_token:
        raise RuntimeError("Missing STRAVA_ACCESS_TOKEN environment variable.")

    response = requests.get(
        STRAVA_ACTIVITIES_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        params={"per_page": 1},
        timeout=30,
    )
    response.raise_for_status()

    activities = response.json()
    if not activities:
        raise RuntimeError("No Strava activities found.")

    return activities[0]


def main():
    activity = fetch_latest_activity()
    print(f"name: {activity.get('name')}")
    print(f"distance: {activity.get('distance')}")
    print(f"moving_time: {activity.get('moving_time')}")


if __name__ == "__main__":
    main()
