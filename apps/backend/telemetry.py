"""Appliance readings, per account.

A plug or meter sensor posts `{device_id, watts, ts}` to `/v1/telemetry` with the
account's token. Until 2026-10-27 the samples sat in one in-memory list shared by
every account, so one person's air conditioner showed up in everyone's suggestions
and vanished on restart.
"""

from __future__ import annotations

from typing import Any

import neon


class TelemetryStore:
    def __init__(self, db: neon.Database | None = None) -> None:
        self.db = db or neon.open_database()

    def add(self, user_id: str, device_id: str, watts: float, ts: str) -> None:
        self.db.query(
            "INSERT INTO telemetry (user_id, device_id, watts, ts) VALUES ($1, $2, $3, $4)",
            [user_id, device_id, watts, ts],
        )

    def since(self, user_id: str, since_iso: str) -> list[dict[str, Any]]:
        rows = self.db.query(
            "SELECT device_id, watts, ts FROM telemetry"
            " WHERE user_id = $1 AND ts >= $2 ORDER BY ts, seq",
            [user_id, since_iso],
        )
        return [
            {"device_id": row["device_id"], "watts": float(row["watts"]), "ts": row["ts"]}
            for row in rows
        ]

    def count(self, user_id: str) -> int:
        return int(self.db.value(
            "SELECT count(*) FROM telemetry WHERE user_id = $1", [user_id]
        ) or 0)

    def clear(self, user_id: str) -> None:
        self.db.query("DELETE FROM telemetry WHERE user_id = $1", [user_id])
