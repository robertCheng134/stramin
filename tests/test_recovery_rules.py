import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from recovery_rules import calculate_recovery


def test_recovery_score_30_is_poor():
    garmin_health = {
        "sleep_hours": "5.8",
        "hrv_status": "low",
        "body_battery": "45",
        "stress": "51",
    }

    recovery = calculate_recovery(garmin_health)

    assert recovery["recovery_score"] == 30
    assert recovery["recovery_level"] == "poor"
