"""The server's clock, in the shapes the API stores and returns.

Event times always come from here, never from a request body: a device clock that
is wrong, or a caller that lies, must not move anything (see `/v1/telemetry`).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


class Clock:
    @staticmethod
    def now_iso() -> str:
        return Clock._iso(datetime.now(timezone.utc))

    @staticmethod
    def ago(days: int = 0, hours: int = 0, minutes: int = 0) -> str:
        return Clock._iso(
            datetime.now(timezone.utc) - timedelta(days=days, hours=hours, minutes=minutes)
        )

    @staticmethod
    def in_days(days: int) -> str:
        """A calendar date `days` from now, as `renews_on` wants it (YYYY-MM-DD)."""
        return (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()

    @staticmethod
    def since_seconds(seconds: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    @staticmethod
    def _iso(moment: datetime) -> str:
        return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")
