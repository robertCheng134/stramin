from dataclasses import asdict, dataclass


@dataclass
class HealthData:
    date: str
    sleep_hours: str
    hrv_status: str
    body_battery_or_energy: str
    resting_hr: str
    stress: str = ""
    source: str = "unknown"

    def to_legacy_dict(self):
        data = {
            "date": self.date,
            "sleep_hours": self.sleep_hours,
            "hrv_status": self.hrv_status,
            "body_battery": self.body_battery_or_energy,
            "body_battery_or_energy": self.body_battery_or_energy,
            "resting_hr": self.resting_hr,
            "source": self.source,
        }
        if self.stress not in (None, ""):
            data["stress"] = self.stress
        return data

    def to_dict(self):
        return asdict(self)


def from_garmin_row(row):
    return HealthData(
        date=row.get("date", ""),
        sleep_hours=row.get("sleep_hours", ""),
        hrv_status=str(row.get("hrv_status", "")).lower(),
        body_battery_or_energy=row.get("body_battery", ""),
        resting_hr=row.get("resting_hr", ""),
        stress=row.get("stress", ""),
        source="garmin_csv",
    )
