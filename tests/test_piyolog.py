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

    result = client.parse(feed)

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

    result = client.parse(feed)

    assert result.sleep_start == "21:00"

    assert result.sleep_end == "6:30"


def test_no_temperature() -> None:

    feed = {"records": []}

    client = PiyologClient("dummy")

    result = client.parse(feed)

    assert result.temperature is None

    assert result.temperature_time is None
