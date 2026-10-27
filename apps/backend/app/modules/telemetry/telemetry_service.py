"""Appliance readings, and the meter maths built on them."""

from __future__ import annotations

import math
from typing import Any, Optional

from app.common.api_error import ApiError
from app.common.clock import Clock
from app.modules.receipt.receipt_repository import ReceiptRepository
from app.modules.suggestion import suggestions
from app.modules.telemetry import meter
from app.modules.telemetry.dtos.reading_dto import ReadingDto
from app.modules.telemetry.telemetry_repository import TelemetryRepository


class TelemetryService:
    def __init__(self, readings: TelemetryRepository, receipts: ReceiptRepository) -> None:
        self.readings = readings
        self.receipts = receipts

    def record(self, account_id: str, dto: ReadingDto) -> dict[str, Any]:
        """One appliance reading, stamped with the server's clock.

        A `ts` in the body is ignored: units left are worked out from the gaps
        between readings, so a device clock that is wrong (or a caller that lies)
        would move someone's meter. A sensor therefore posts each sample as it
        takes it.
        """
        if not math.isfinite(dto.watts) or dto.watts < 0:
            raise ApiError(400, "bad_watts", "watts must be a number of 0 or more")
        device_id = dto.device_id.strip()[:64] or "unknown"
        self.readings.add(account_id, device_id, dto.watts, Clock.now_iso())
        return {"accepted": True, "count": self.readings.count(account_id)}

    def meter_reading(self, account_id: str,
                      bills: dict[str, dict]) -> tuple[Optional[float], Optional[int]]:
        """Units left and days left — see `meter.py` for how. None without electricity."""
        if not any(b["kind"] == "electricity" for b in bills.values()):
            return None, None
        units, first_at = self.receipts.units_bought(account_id)
        readings = self.readings.since(account_id, first_at) if first_at else []
        return meter.reading(units_bought=units, first_top_up_at=first_at, readings=readings)

    def recent_load(self, account_id: str) -> list[dict[str, Any]]:
        """The readings the load-imbalance suggestion looks at."""
        return self.readings.since(
            account_id, Clock.since_seconds(suggestions.LOAD_LOOKBACK_SECONDS)
        )
