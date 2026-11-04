from __future__ import annotations

from xml.sax.saxutils import escape

_HEAD = '<?xml version="1.0" encoding="UTF-8"?>'


class Twiml:
    """The reply Twilio reads back from the webhook: one SMS, or none."""

    @staticmethod
    def message(text: str | None) -> str:
        """`None` → an empty `<Response/>`, so Twilio sends nothing (a duplicate)."""
        if text is None:
            return f"{_HEAD}<Response/>"
        return f"{_HEAD}<Response><Message>{escape(text)}</Message></Response>"
