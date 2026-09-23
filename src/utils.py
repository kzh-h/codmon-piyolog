from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def get_jst_date() -> date:
    return datetime.now(JST).date()


def to_jst(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(
        JST
    )


def round_to_15min(dt: datetime) -> str:
    minute = dt.minute

    rounded = round(minute / 15) * 15

    if rounded == 60:
        dt = dt + timedelta(hours=1)
        rounded = 0

    return f"{dt.hour}:{rounded:02d}"
