"""E.164, the only key a phone channel's sender gets (HANDOFF §8A).

WhatsApp names a sender by its `wa_id` (`2348012345678`, no plus); Twilio sends
`+2348012345678`. Both land on the same E.164 string, so one person is one
identity whichever door they knock on. Never a display name.
"""

from __future__ import annotations

import re

_E164 = re.compile(r"^\+[1-9]\d{6,14}$")


class PhoneNumber:
    @staticmethod
    def e164(raw: str) -> str | None:
        """`2348012345678` or `+2348012345678` → `+2348012345678`; anything else → None.

        A sender that is not a phone number is refused, not coerced: a key that
        might be wrong is worse than no key.
        """
        candidate = raw.strip()
        if not candidate.startswith("+"):
            candidate = f"+{candidate}"
        return candidate if _E164.match(candidate) else None

    @staticmethod
    def redact(e164: str) -> str:
        """What a log line may say about a number: its last four digits."""
        return f"…{e164[-4:]}"
