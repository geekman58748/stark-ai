from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SmsConfig:
    """Twilio's auth token (required, or the door refuses everything) and the
    public webhook URL Twilio signs (optional; pin it behind a TLS proxy)."""

    auth_token: Optional[str]
    webhook_url: Optional[str]

    @classmethod
    def from_env(cls) -> "SmsConfig":
        return cls(
            auth_token=os.environ.get("TWILIO_AUTH_TOKEN") or None,
            webhook_url=os.environ.get("TWILIO_WEBHOOK_URL") or None,
        )
