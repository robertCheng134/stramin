import csv
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from garmin_health import load_garmin_health_rows
from integrations import apple_health, manual_input, samsung_health
from integrations.garmin_csv import load_health_data


def _write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "date",
                "sleep_hours",
                "hrv_status",
                "body_battery",
                "resting_hr",
                "stress",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def test_garmin_csv_adapter_returns_unified_health_data(tmp_path):
    csv_path = tmp_path / "garmin.csv"
    _write_csv(
        csv_path,
        [
            {
                "date": "2026-05-07",
                "sleep_hours": "7.2",
                "hrv_status": "balanced",
                "body_battery": "75",
                "resting_hr": "52",
                "stress": "20",
            }
        ],
    )

    health_data = load_health_data(csv_path)[0]

    assert health_data.date == "2026-05-07"
    assert health_data.body_battery_or_energy == "75"
    assert health_data.source == "garmin_csv"


def test_garmin_health_facade_keeps_legacy_body_battery_key(tmp_path):
    csv_path = tmp_path / "garmin.csv"
    _write_csv(
        csv_path,
        [
            {
                "date": "2026-05-07",
                "sleep_hours": "7.2",
                "hrv_status": "balanced",
                "body_battery": "75",
                "resting_hr": "52",
                "stress": "",
            }
        ],
    )

    row = load_garmin_health_rows(csv_path)[0]

    assert row["body_battery"] == "75"
    assert row["body_battery_or_energy"] == "75"
    assert row["source"] == "garmin_csv"


def test_placeholder_integrations_are_not_implemented():
    for integration in (apple_health, samsung_health, manual_input):
        with pytest.raises(NotImplementedError):
            integration.load_health_rows()
