"""Units left and days left on a prepaid meter, from data the account really has.

There is no live meter reading yet, so neither number may be invented (they were:
11.4 units and "4 days left" for everybody, forever). What we do know:

- **Units bought** — every delivered electricity top-up carries the units it vended.
- **Energy used** — the account's own appliance readings (`telemetry_repository.py`), each a
  watts sample at a moment. Between two samples of one device the draw is taken as
  the earlier sample's, for at most `MAX_GAP_SECONDS`: a plug that went quiet for a
  day is not assumed to have run flat out all day.

So `units_left = units bought - kWh measured since the first top-up`, and
`days_left = units_left / measured kWh a day`. With no top-up there are no units to
count down; with no readings there is no pace, and days left is None rather than a
guess. Measured use only covers the devices that report, so it can only ever
under-count — the honest direction for a "you have N days" line is to say so in
the copy, not to pad the number.

Pure functions, no store, no clock of their own — like `suggestions.py`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

MAX_GAP_SECONDS = 15 * 60
# Days of readings the daily pace is taken over.
PACE_LOOKBACK_DAYS = 7
# Less measured time than this says nothing about a day.
MIN_COVERED_SECONDS = 60 * 60


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip().replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _intervals(readings: Iterable[dict]) -> list[tuple[datetime, float, float]]:
    """(start, seconds, watts) for each measured stretch, across all devices."""
    by_device: dict[str, list[tuple[datetime, float]]] = {}
    for reading in readings:
        when = _parse_ts(reading.get("ts"))
        if when is None:
            continue
        by_device.setdefault(str(reading.get("device_id") or "unknown"), []).append(
            (when, float(reading["watts"]))
        )
    stretches: list[tuple[datetime, float, float]] = []
    for samples in by_device.values():
        samples.sort(key=lambda sample: sample[0])
        for (start, watts), (end, _) in zip(samples, samples[1:]):
            seconds = min((end - start).total_seconds(), MAX_GAP_SECONDS)
            if seconds > 0:
                stretches.append((start, seconds, watts))
    return stretches


def kwh_used(readings: Iterable[dict]) -> float:
    return sum(seconds * watts for _, seconds, watts in _intervals(readings)) / 3_600_000


def _covered_seconds(stretches: list[tuple[datetime, float, float]]) -> float:
    """Clock time with at least one device measured. Two devices reporting over the
    same hour are one measured hour, not two."""
    spans = sorted((start, start + timedelta(seconds=seconds))
                   for start, seconds, _ in stretches)
    total = 0.0
    current_start, current_end = None, None
    for start, end in spans:
        if current_end is None or start > current_end:
            if current_end is not None:
                total += (current_end - current_start).total_seconds()
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    if current_end is not None:
        total += (current_end - current_start).total_seconds()
    return total


def kwh_per_day(readings: Iterable[dict], *, now: datetime) -> float | None:
    """Measured pace over the lookback window, or None if too little was measured."""
    cutoff = now - timedelta(days=PACE_LOOKBACK_DAYS)
    recent = [s for s in _intervals(readings) if s[0] >= cutoff]
    energy = sum(seconds * watts for _, seconds, watts in recent)
    measured = _covered_seconds(recent)
    if measured < MIN_COVERED_SECONDS or energy <= 0:
        return None
    return energy / 3_600_000 / measured * 86_400


def reading(*, units_bought: float, first_top_up_at: str | None,
            readings: list[dict], now: datetime | None = None) -> tuple[float | None, int | None]:
    """(units_left, days_left) for one account's meter.

    `readings` should already start at the first top-up (the store query does that):
    energy used before there were any units on the meter is not theirs to subtract.
    """
    if first_top_up_at is None or units_bought <= 0:
        return None, None
    now = now or datetime.now(timezone.utc)
    units_left = round(max(units_bought - kwh_used(readings), 0.0), 2)
    pace = kwh_per_day(readings, now=now)
    days_left = int(units_left / pace) if pace else None
    return units_left, days_left
