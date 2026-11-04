"""Twilio's `X-Twilio-Signature`: base64(HMAC-SHA1(auth token, url + params)).

`params` is the POST form, sorted by name; each name is followed by its value.
A repeated name contributes each of its distinct values in sorted order, which
is what Twilio's own `RequestValidator` does. The URL must be the exact public
URL Twilio was given — scheme, host, path and query — so behind a proxy that
terminates TLS it is pinned with `TWILIO_WEBHOOK_URL`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac


class TwilioSignature:
    @staticmethod
    def compute(auth_token: str, url: str, params: dict[str, list[str]]) -> str:
        signed = url + "".join(
            name + value
            for name in sorted(params)
            for value in sorted(set(params[name]))
        )
        digest = hmac.new(auth_token.encode(), signed.encode(), hashlib.sha1).digest()
        return base64.b64encode(digest).decode()

    @staticmethod
    def valid(auth_token: str, url: str, params: dict[str, list[str]],
              header_value: str) -> bool:
        expected = TwilioSignature.compute(auth_token, url, params)
        return hmac.compare_digest(header_value.encode(), expected.encode())
