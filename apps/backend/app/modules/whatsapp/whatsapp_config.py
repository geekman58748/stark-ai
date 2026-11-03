from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class WhatsAppConfig:
    """The four settings the WhatsApp door needs; with any one missing it refuses everything."""

    access_token: Optional[str]
    phone_number_id: Optional[str]
    app_secret: Optional[str]
    verify_token: Optional[str]

    @classmethod
    def from_env(cls) -> "WhatsAppConfig":
        return cls(
            access_token=os.environ.get("WHATSAPP_ACCESS_TOKEN") or None,
            phone_number_id=os.environ.get("WHATSAPP_PHONE_NUMBER_ID") or None,
            app_secret=os.environ.get("WHATSAPP_APP_SECRET") or None,
            verify_token=os.environ.get("WHATSAPP_VERIFY_TOKEN") or None,
        )
