"""Units left and days left from purchases and readings (`meter.py`). No network."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

import meter

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def at(minutes_ago: float) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def samples(device: str, watts: float, *, every: int, count: int, start_ago: int):
    return [{"device_id": device, "watts": watts, "ts": at(start_ago - i * every)}
            for i in range(count)]


class ReadingTest(unittest.TestCase):
    def test_no_top_up_means_no_units(self):
        self.assertEqual(
            meter.reading(units_bought=0, first_top_up_at=None, readings=[], now=NOW),
            (None, None),
        )

    def test_units_without_readings_have_no_pace(self):
        self.assertEqual(
            meter.reading(units_bought=23.92, first_top_up_at=at(600), readings=[], now=NOW),
            (23.92, None),
        )

    def test_a_kilowatt_for_two_hours_uses_two_units(self):
        # Every 10 minutes for two hours: 12 stretches of 10 minutes at 1 kW.
        readings = samples("ac", 1000, every=10, count=13, start_ago=120)
        units_left, days_left = meter.reading(
            units_bought=50, first_top_up_at=at(600), readings=readings, now=NOW
        )
        self.assertEqual(units_left, 48.0)
        # 1 kW is 24 kWh a day; 48 units is two days.
        self.assertEqual(days_left, 2)

    def test_a_silent_device_is_not_assumed_to_run_flat_out(self):
        # Two samples a day apart count as one capped 15-minute stretch, not 24 hours.
        readings = [{"device_id": "ac", "watts": 2000, "ts": at(1440)},
                    {"device_id": "ac", "watts": 2000, "ts": at(0)}]
        self.assertAlmostEqual(meter.kwh_used(readings), 0.5)

    def test_two_devices_at_once_are_one_measured_hour(self):
        readings = (samples("ac", 1000, every=10, count=7, start_ago=60)
                    + samples("fridge", 200, every=10, count=7, start_ago=60))
        # 1.2 kW over one clock hour, not 1.2 kWh spread over two hours.
        self.assertAlmostEqual(meter.kwh_per_day(readings, now=NOW), 1.2 * 24)

    def test_too_little_measured_time_gives_no_pace(self):
        readings = samples("ac", 1000, every=10, count=3, start_ago=20)
        self.assertIsNone(meter.kwh_per_day(readings, now=NOW))

    def test_units_never_go_below_zero(self):
        readings = samples("heater", 3000, every=15, count=40, start_ago=600)
        units_left, days_left = meter.reading(
            units_bought=1, first_top_up_at=at(700), readings=readings, now=NOW
        )
        self.assertEqual((units_left, days_left), (0.0, 0))


if __name__ == "__main__":
    unittest.main()
