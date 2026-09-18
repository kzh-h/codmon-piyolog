from typing import Any

import requests

from .models import CodmonData
from .utils import round_to_15min, to_jst


class PiyologClient:
    def __init__(self, feed_url: str):
        self.feed_url = feed_url

    def fetch(self) -> dict[str, Any]:
        return requests.get(self.feed_url, timeout=30).json()  # type: ignore[no-any-return]

    def parse(self, feed: dict[str, Any] | None = None) -> CodmonData:
        if feed is None:
            feed = self.fetch()

        poop_evening = 0
        poop_morning = 0

        latest_sleep = None
        latest_wakeup = None
        latest_temp = None

        for record in feed["records"]:
            dt = to_jst(record["datetime"])

            t = record["type"]

            if t == "Poop":
                if 16 <= dt.hour <= 23:
                    poop_evening += 1

                elif dt.hour < 7 or (dt.hour == 7 and dt.minute <= 30):
                    poop_morning += 1

            elif t == "Sleep":
                latest_sleep = dt

            elif t == "WakeUp":
                latest_wakeup = dt

            elif t == "Temperature":
                latest_temp = record

        sleep_start = None
        sleep_end = None

        if latest_sleep:
            sleep_start = round_to_15min(latest_sleep)

        if latest_wakeup:
            sleep_end = round_to_15min(latest_wakeup)

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
        )
