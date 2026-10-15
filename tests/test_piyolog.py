from datetime import date

from src.piyolog import PiyologClient


def test_parse_feed() -> None:

    feed = {
        "records": [
            {
                "datetime": "2026-09-15T10:05:00.000Z",
                "type": "Poop",
            },
            {
                "datetime": "2026-09-15T12:00:00.000Z",
                "type": "Sleep",
            },
            {
                "datetime": "2026-09-15T21:30:00.000Z",
                "type": "WakeUp",
            },
            {
                "datetime": "2026-09-15T22:10:00.000Z",
                "type": "Temperature",
                "value": {
                    "value": 36.8,
                    "unit": "celsius",
                },
            },
        ]
    }

    client = PiyologClient("dummy")

    result = client.parse(feed, current_date=date(2026, 9, 16))

    assert result.poop_evening_count == 1

    assert result.poop_morning_count == 0

    assert result.sleep_start == "21:00"

    assert result.sleep_end == "6:30"

    assert result.temperature == "36.8"

    assert result.temperature_time == "7:15"


def test_sleep_only() -> None:

    feed = {
        "records": [
            {
                "datetime": "2026-09-15T12:00:00.000Z",
                "type": "Sleep",
            },
            {
                "datetime": "2026-09-15T21:30:00.000Z",
                "type": "WakeUp",
            },
        ]
    }

    client = PiyologClient("dummy")

    result = client.parse(feed, current_date=date(2026, 9, 16))

    assert result.sleep_start == "21:00"

    assert result.sleep_end == "6:30"


def test_no_temperature() -> None:

    feed = {"records": []}

    client = PiyologClient("dummy")

    result = client.parse(feed, current_date=date(2026, 9, 16))

    assert result.temperature is None

    assert result.temperature_time is None


def _rec(utc: str, type_: str, temp: float | None = None) -> dict:  # type: ignore[type-arg]
    rec: dict = {"datetime": f"{utc}.000Z", "type": type_}  # type: ignore[type-arg]
    if temp is not None:
        rec["value"] = {"value": temp, "unit": "celsius"}
    return rec


def _parse(records: list):  # type: ignore[no-untyped-def, type-arg]
    return PiyologClient("dummy").parse(
        {"records": records}, current_date=date(2026, 9, 16)
    )


def test_morning_poop_boundary_0830() -> None:
    # JST 8:30 (= 2026-09-15T23:30Z) は含み、8:31 は含まない
    result = _parse(
        [
            _rec("2026-09-15T23:30:00", "Poop"),
            _rec("2026-09-15T23:31:00", "Poop"),
        ]
    )

    assert result.poop_morning_count == 1


def test_morning_poop_only_current_day() -> None:
    # 前日 JST 6:00 の朝のうんちは数えない
    result = _parse(
        [
            _rec("2026-09-14T21:00:00", "Poop"),
            _rec("2026-09-15T21:00:00", "Poop"),
        ]
    )

    assert result.poop_morning_count == 1


def test_evening_poop_only_previous_day() -> None:
    # 前日 JST 16:00 は数え、前々日と当日の夕方は数えない
    result = _parse(
        [
            _rec("2026-09-15T07:00:00", "Poop"),
            _rec("2026-09-14T07:00:00", "Poop"),
            _rec("2026-09-16T07:00:00", "Poop"),
        ]
    )

    assert result.poop_evening_count == 1


def test_wakeup_until_0830() -> None:
    # JST 8:30 は採用、8:31 は不採用
    ok = _parse([_rec("2026-09-15T23:30:00", "WakeUp")])
    ng = _parse([_rec("2026-09-15T23:31:00", "WakeUp")])

    assert ok.sleep_end == "8:30"
    assert ng.sleep_end is None


def test_temperature_latest_within_0830() -> None:
    # 当日 0:00-8:30 のうち最も遅い記録を採用 (8:31 と前日は除外)
    result = _parse(
        [
            _rec("2026-09-15T21:00:00", "Temperature", 36.5),  # 6:00
            _rec("2026-09-15T23:15:00", "Temperature", 36.9),  # 8:15
            _rec("2026-09-15T23:31:00", "Temperature", 38.0),  # 8:31
            _rec("2026-09-15T10:00:00", "Temperature", 37.5),  # 前日 19:00
        ]
    )

    assert result.temperature == "36.9"
    assert result.temperature_time == "8:15"


def test_temperature_latest_not_last_in_feed() -> None:
    # フィード順ではなく時刻で最も遅いものを選ぶ
    result = _parse(
        [
            _rec("2026-09-15T23:00:00", "Temperature", 36.9),  # 8:00
            _rec("2026-09-15T21:00:00", "Temperature", 36.5),  # 6:00
        ]
    )

    assert result.temperature == "36.9"


def test_temperature_outside_range_is_none() -> None:
    result = _parse(
        [_rec("2026-09-16T01:00:00", "Temperature", 36.8)]
    )  # 10:00

    assert result.temperature is None
