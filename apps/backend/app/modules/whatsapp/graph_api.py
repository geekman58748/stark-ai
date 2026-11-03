"""Meta's Graph API, the four calls the WhatsApp door makes (Cloud API v21.0).

- `media`: a voice note's id → its short-lived URL → the bytes. Both hops carry
  the bearer token; the URL alone returns nothing. The size Meta reports is
  checked before the download, and the read is bounded either way.
- `send_text`, `upload_audio`, `send_audio`: the reply, as text or as an OGG/Opus
  voice note.

Every call returns None/False on any failure and never raises: a number that
cannot be reached is not an error, and the caller falls back to text.
Response shapes are modelled on Meta's published docs, not captured live.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from typing import Any

GRAPH_API = "https://graph.facebook.com/v21.0"


class GraphApi:
    def __init__(self, access_token: str, phone_number_id: str, *,
                 base: str = GRAPH_API, timeout: float = 20.0) -> None:
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.base = base.rstrip("/")
        self.timeout = timeout

    def media(self, media_id: str, *, max_bytes: int) -> bytes | None:
        info = self._json("GET", f"{self.base}/{media_id}")
        if info is None or not info.get("url"):
            return None
        if int(info.get("file_size") or 0) > max_bytes:
            return None
        data = self._call("GET", info["url"], max_bytes=max_bytes)
        return data or None

    def send_text(self, to: str, text: str) -> bool:
        return self._message(to, {"type": "text",
                                  "text": {"preview_url": False, "body": text}})

    def send_audio(self, to: str, media_id: str) -> bool:
        return self._message(to, {"type": "audio", "audio": {"id": media_id}})

    def upload_audio(self, ogg: bytes) -> str | None:
        """OGG/Opus → a media id `send_audio` can reference."""
        boundary = f"----starkwa{uuid.uuid4().hex}"
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="messaging_product"'
            f"\r\n\r\nwhatsapp\r\n"
            f'--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\n'
            f"audio/ogg\r\n"
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="voice.ogg"\r\nContent-Type: audio/ogg\r\n\r\n'
        ).encode() + ogg + f"\r\n--{boundary}--\r\n".encode()
        info = self._json("POST", f"{self.base}/{self.phone_number_id}/media", body,
                          f"multipart/form-data; boundary={boundary}")
        return info.get("id") if info else None

    def _message(self, to: str, content: dict[str, Any]) -> bool:
        payload = {"messaging_product": "whatsapp", "recipient_type": "individual",
                   "to": to.lstrip("+"), **content}
        return self._json("POST", f"{self.base}/{self.phone_number_id}/messages",
                          json.dumps(payload).encode(), "application/json") is not None

    def _json(self, method: str, url: str, body: bytes | None = None,
              content_type: str | None = None) -> dict[str, Any] | None:
        raw = self._call(method, url, body, content_type)
        if raw is None:
            return None
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return None

    def _call(self, method: str, url: str, body: bytes | None = None,
              content_type: str | None = None, *, max_bytes: int = 1024 * 1024) -> bytes | None:
        headers = {"Authorization": f"Bearer {self.access_token}"}
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                data = res.read(max_bytes + 1)
        except urllib.error.HTTPError as err:
            err.close()
            return None
        except (urllib.error.URLError, TimeoutError, OSError):
            return None
        return data if len(data) <= max_bytes else None
