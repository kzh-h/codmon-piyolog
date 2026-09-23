from datetime import date, datetime, timedelta
from typing import Any

import requests

from .models import CodmonData
from .utils import get_jst_date, round_to_15min, to_jst


class PiyologClient:
    def __init__(self, feed_url: str):
        self.feed_url = feed_url

    def fetch(self) -> dict[str, Any]:
        return requests.get(self.feed_url, timeout=30).json()  # type: ignore[no-any-return]

    def _determine_current_day(self, records: list[dict[str, Any]]) -> date:
        morning_dates: list[date] = []
        for record in records:
            dt = to_jst(record["datetime"])
            if record["type"] in ("WakeUp", "Temperature"):
                morning_dates.append(dt.date())
        if morning_dates:
            return min(morning_dates)
        all_dates = [to_jst(r["datetime"]).date() for r in records]
        return max(all_dates) if all_dates else get_jst_date()

    def parse(self, feed: dict[str, Any] | None = None) -> CodmonData:
        if feed is None:
            feed = self.fetch()

        records = feed["records"]
        current_day = self._determine_current_day(records)
        previous_day = current_day - timedelta(days=1)

        poop_evening = 0
        poop_morning = 0

        sleep_start_dt: datetime | None = None
        sleep_end_dt: datetime | None = None
        latest_temp = None

        for record in records:
            dt = to_jst(record["datetime"])
            t = record["type"]

            if t == "Poop":
                if 16 <= dt.hour <= 23:
                    poop_evening += 1
                elif dt.hour < 7 or (dt.hour == 7 and dt.minute <= 30):
                    poop_morning += 1

            elif t == "Sleep":
                if (
                    dt.date() == previous_day
                    and 19 <= dt.hour <= 23
                    and (sleep_start_dt is None or dt > sleep_start_dt)
                ):
                    sleep_start_dt = dt

            elif t == "WakeUp":
                if (
                    dt.date() == current_day
                    and (dt.hour < 7 or (dt.hour == 7 and dt.minute <= 30))
                    and (sleep_end_dt is None or dt < sleep_end_dt)
                ):
                    sleep_end_dt = dt

            elif t == "Temperature":
                latest_temp = record

        sleep_start = (
            round_to_15min(sleep_start_dt) if sleep_start_dt else None
        )
        sleep_end = round_to_15min(sleep_end_dt) if sleep_end_dt else None

        temperature = None
        temperature_time = None

        if latest_temp:
            temperature = str(latest_temp["value"]["value"])
            dt = to_jst(latest_temp["datetime"])
            temperature_time = round_to_15min(dt)

        return CodmonData(
            poop_evening_count=poop_evening,
            poop_morning_count=poop_morning,
            sleep_start=sleep_start,
            sleep_end=sleep_end,
            temperature=temperature,
            temperature_time=temperature_time,
            mood_evening="普通",
            mood_morning="普通",
        )
