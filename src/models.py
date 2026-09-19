from dataclasses import dataclass


@dataclass
class CodmonData:
    poop_evening_count: int
    poop_morning_count: int

    sleep_start: str | None
    sleep_end: str | None

    temperature: str | None
    temperature_time: str | None

    mood_evening: str | None
    mood_morning: str | None
