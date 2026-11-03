"""Bachs — the naira rail. Standard library only, like `vtpass.py`.

Where each money movement goes through Bachs, and why that endpoint:

| Movement | Endpoint | Why this one |
|---|---|---|
| User adds money | `POST /v1/checkout-sessions` | One session per deposit carries our `reference` and `metadata` back on `collection.succeeded`. A Bachs virtual account is one per *merchant*, with no reference, so it cannot say which user paid. The hosted page takes bank transfer, card and stablecoins. |
| User withdraws | `POST /v1/payouts/destinations` → `POST /v1/payouts` | A destination must pass Bachs's review (`is_usable`) before it can be paid. |
| VTpass float refill | `POST /v1/payouts` to a fixed destination | Same rail, a destination Stark registers once. |
| Float and treasury view | `GET /v1/balances` | |

Amounts on the wire are **decimal strings in naira** (`"5000.00"`), never kobo. This
codebase is integer naira, so conversion happens here and nowhere else.

Webhooks are signed: `X-Bachs-Signature-V2: t=<unix>,v1=<hex>[,v1=<hex>]`, the HMAC-
SHA256 of `"<t>.<raw body>"` with the endpoint secret. During a secret rotation two
`v1` values arrive and either may match. `X-Bachs-Signature` (+ `X-Bachs-Timestamp`)
is the older single-signature form and is accepted too.

Configuration: `BACHS_SECRET_KEY` (`sk_sandbox_…` or `sk_live_…`; the prefix picks
the host), `BACHS_WEBHOOK_SECRET`. Unset = Bachs is off, and the routes that need it
answer 503 `not_available` instead of pretending.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Any, Mapping, Optional

SANDBOX_URL = "https://sandbox-api.bachs.io"
LIVE_URL = "https://api.bachs.io"
USER_AGENT = "stark-backend/1.0 (+https://hellostark.xyz)"
SIGNATURE_TOLERANCE_SECONDS = 300


class BachsError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message


def naira(amount_ngn: int) -> str:
    return f"{amount_ngn}.00"


def whole_naira(amount: str) -> int:
    """`"249700.00"` → 249700. Kobo are dropped, never rounded up into credit."""
    return int(Decimal(amount).to_integral_value(rounding=ROUND_DOWN))


@dataclass(frozen=True)
class BachsClient:
    secret_key: str
    base_url: str
    timeout: int = 20

    # --- deposits ---------------------------------------------------------------

    def create_checkout(self, *, amount_ngn: int, reference: str, metadata: dict[str, str],
                        success_url: Optional[str], expires_in_minutes: int) -> dict[str, Any]:
        body: dict[str, Any] = {
            "pricing": {"currency": "NGN", "amount": naira(amount_ngn), "price_type": "fixed"},
            "payment_method_types": ["NGN_BANK_TRANSFER", "NGN_CARD", "CRYPTO"],
            "reference": reference,
            "metadata": metadata,
            "expires_in_minutes": expires_in_minutes,
        }
        if success_url:
            body["success_url"] = success_url
        return self._request("POST", "/v1/checkout-sessions", body, idempotency_key=reference)

    def get_checkout(self, checkout_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/checkout-sessions/{checkout_id}")

    # --- withdrawals and refills ------------------------------------------------

    def banks(self) -> list[dict[str, str]]:
        return self._request("GET", "/v1/reference/banks?country=NG")["banks"]

    def resolve_account(self, bank_code: str, account_number: str) -> dict[str, Any]:
        return self._request("POST", "/v1/misc/bank-accounts/resolve", {
            "account_number": account_number, "bank_code": bank_code, "country": "NG",
        })

    def create_destination(self, *, bank_code: str, account_number: str, name: str,
                           metadata: dict[str, str]) -> dict[str, Any]:
        return self._request("POST", "/v1/payouts/destinations", {
            "type": "bank_account", "currency": "NGN", "bank_code": bank_code,
            "account_number": account_number, "name": name, "metadata": metadata,
        })

    def get_destination(self, destination_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/payouts/destinations/{destination_id}")

    def create_payout(self, *, destination: str, amount_ngn: int, reference: str,
                      narration: str) -> dict[str, Any]:
        """`reference` doubles as the idempotency key: a retry is the same payout."""
        return self._request("POST", "/v1/payouts", {
            "destination": destination, "amount": naira(amount_ngn),
            "reference": reference, "narration": narration[:15],
        }, idempotency_key=reference)

    def get_payout(self, payout_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/payouts/{payout_id}")

    def ngn_balance(self) -> int:
        balances = self._request("GET", "/v1/balances")["balances"]
        ngn = next((b for b in balances if b["currency"] == "NGN"), None)
        return whole_naira(ngn["available_balance"]) if ngn else 0

    # --- plumbing ---------------------------------------------------------------

    def _request(self, method: str, path: str, body: Optional[dict] = None, *,
                 idempotency_key: Optional[str] = None) -> Any:
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Accept": "application/json",
            # Bachs sits behind Cloudflare, which answers Python's default
            # `Python-urllib/x` agent with 403 (error 1010) before Bachs sees it.
            "User-Agent": USER_AGENT,
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        request = urllib.request.Request(self.base_url + path, data=data, method=method,
                                         headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as err:
            try:
                payload = json.loads(err.read() or b"{}")
            except json.JSONDecodeError:
                payload = {}
            finally:
                err.close()
            raise BachsError(err.code, payload.get("error_code") or "http_error",
                             payload.get("detail") or f"HTTP {err.code}") from err
        except urllib.error.URLError as err:
            raise BachsError(0, "unreachable", f"Could not reach Bachs: {err}") from err


def client_from_env(env: Optional[Mapping[str, str]] = None) -> Optional[BachsClient]:
    source = os.environ if env is None else env
    key = (source.get("BACHS_SECRET_KEY") or "").strip()
    if not key:
        return None
    if key.startswith("sk_live_"):
        return BachsClient(key, LIVE_URL)
    if key.startswith("sk_sandbox_"):
        return BachsClient(key, SANDBOX_URL)
    raise ValueError("BACHS_SECRET_KEY must start with sk_live_ or sk_sandbox_")


def verify_signature(raw_body: bytes, headers: Mapping[str, str], secret: str, *,
                     now: Optional[float] = None) -> bool:
    """True when the body was signed by Bachs with `secret`, recently.

    Checked on the raw bytes before anything parses them. `headers` must be
    case-insensitive (Starlette's are).
    """
    if not secret:
        return False
    timestamp, signatures = _signature_parts(headers)
    if timestamp is None or not signatures:
        return False
    try:
        age = abs((time.time() if now is None else now) - int(timestamp))
    except ValueError:
        return False
    if age > SIGNATURE_TOLERANCE_SECONDS:
        return False
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + raw_body,
                        hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, candidate) for candidate in signatures)


def _signature_parts(headers: Mapping[str, str]) -> tuple[Optional[str], list[str]]:
    v2 = headers.get("x-bachs-signature-v2")
    if v2:
        timestamp, signatures = None, []
        for part in v2.split(","):
            key, _, value = part.strip().partition("=")
            if key == "t":
                timestamp = value
            elif key == "v1" and value:
                signatures.append(value)
        return timestamp, signatures
    v1 = headers.get("x-bachs-signature")
    return headers.get("x-bachs-timestamp"), [v1] if v1 else []
