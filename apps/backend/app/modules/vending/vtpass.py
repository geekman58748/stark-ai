#!/usr/bin/env python3
"""VTpass client for Stark — zero dependencies, dry-run by default.

Confirmed against the live sandbox on 2026-10-20:
  GET  /service-variations?serviceID=ikeja-electric  -> 200, codes: prepaid, postpaid
  POST /merchant-verify                              -> 401 "Invalid Credentials" without auth
  auth: sandbox uses basic auth (username/password); API-key headers also supported
  response codes: 000 ok, 018 low balance, 019 duplicate, 030 biller unreachable,
                  099 processing, 083 system error

Two rules this client enforces, because the agent's copy depends on them:

1. Never report success unless `code == "000"` AND `transactions.status == "delivered"`.
   A `pending` transaction may still produce a token later.
2. Retries of the same purchase MUST reuse the same `request_id`, or VTpass
   treats it as a second transaction (code 019 = duplicate).

Usage (dry-run shows the full flow with no keys):
    python3 vtpass.py variations
    python3 vtpass.py verify  --meter 04512345678
    python3 vtpass.py buy     --meter 04512345678 --amount 5000 --phone 08031234567
    python3 vtpass.py buy --fixture pay_pending.json       # exercise the pending path

Add --live to hit the real API. Needs credentials in the environment:
    VTPASS_ENV=sandbox
    VTPASS_USERNAME=... VTPASS_PASSWORD=...            (basic auth, sandbox default)
    VTPASS_API_KEY=... VTPASS_PUBLIC_KEY=... VTPASS_SECRET_KEY=...   (optional)
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_URLS = {
    "sandbox": "https://sandbox.vtpass.com/api",
    "production": "https://vtpass.com/api",
}

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"

# Business outcome codes. Anything not "000" is a failure to tell the user about.
CODE_MESSAGES = {
    "000": "Successful",
    "011": "Missing or invalid arguments",
    "012": "That bill product does not exist",
    "016": "Invalid meter or phone number",
    "018": "VTpass wallet balance is too low",
    "019": "Duplicate transaction",
    "020": "Biller confirmed",
    "021": "Account locked",
    "028": "This product is not enabled on the account",
    "030": "The meter provider is unreachable",
    "034": "This service is suspended",
    "083": "VTpass system error",
    "099": "Transaction still processing",
}

# Worth retrying with the SAME request_id.
RETRYABLE_CODES = {"030", "083"}

TOKEN_RE = re.compile(r"(\d{4}(?:[ -]?\d{4}){4})")


class VtpassError(Exception):
    """A VTpass failure. `code` is the machine-readable VTpass code."""

    def __init__(
        self,
        code: str,
        description: str = "",
        *,
        http_status: int | None = None,
        raw: Any = None,
    ):
        self.code = code
        self.description = description or CODE_MESSAGES.get(code, "VTpass error")
        self.http_status = http_status
        self.raw = raw
        super().__init__(f"{code}: {self.description}")

    @property
    def retryable(self) -> bool:
        return self.code in RETRYABLE_CODES

    @property
    def user_message(self) -> str:
        """Plain-English line the agent can say out loud. No jargon."""
        return {
            "016": "I couldn't find that meter. Can you check the number?",
            "018": "My VTpass float is low, so I can't buy that right now.",
            "019": "That looks like it already went through. Let me check before trying again.",
            "030": "The meter provider isn't responding. Want me to try again?",
            "034": "Meter top-ups are paused on the provider's side.",
        }.get(self.code, "That payment didn't go through. Nothing was charged.")


@dataclass
class VendingResult:
    request_id: str
    code: str
    status: str
    token: str | None = None
    units: str | None = None
    amount_ngn: int | None = None
    description: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def delivered(self) -> bool:
        """True only when the token is actually in hand."""
        return self.code == "000" and self.status.lower() == "delivered"

    @property
    def pending(self) -> bool:
        return self.status.lower() in {"pending", "initiated"} or self.code == "099"


def new_request_id() -> str:
    """VTpass convention: minute-precision timestamp plus a random suffix."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    return f"{stamp}{uuid.uuid4().hex[:8]}"


def extract_token(raw: dict) -> str | None:
    """Find the 20-digit token wherever VTpass decided to put it."""
    txn = (raw.get("content") or {}).get("transactions") or {}
    for candidate in (
        txn.get("token"),
        txn.get("purchased_code"),
        raw.get("purchased_code"),
        raw.get("token"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            match = TOKEN_RE.search(candidate)
            if match:
                return re.sub(r"[ -]", "", match.group(1))
            # keep any non-empty value; caller decides how to display it
            return candidate.strip()
    return None


class VtpassClient:
    def __init__(
        self,
        *,
        env: str | None = None,
        dry_run: bool = True,
        timeout: int = 30,
        fixture: str | None = None,
        username: str | None = None,
        password: str | None = None,
        api_key: str | None = None,
        public_key: str | None = None,
        secret_key: str | None = None,
    ):
        self.env = (env or os.environ.get("VTPASS_ENV") or "sandbox").lower()
        if self.env not in BASE_URLS:
            raise ValueError(f"VTPASS_ENV must be one of {list(BASE_URLS)}")
        self.base = BASE_URLS[self.env]
        self.dry_run = dry_run
        self.timeout = timeout
        self.fixture = fixture

        self.username = username or os.environ.get("VTPASS_USERNAME")
        self.password = password or os.environ.get("VTPASS_PASSWORD")
        self.api_key = api_key or os.environ.get("VTPASS_API_KEY")
        self.public_key = public_key or os.environ.get("VTPASS_PUBLIC_KEY")
        self.secret_key = secret_key or os.environ.get("VTPASS_SECRET_KEY")

    # --- transport ---------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.username and self.password:
            blob = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            headers["Authorization"] = f"Basic {blob}"
        if self.api_key:
            headers["api-key"] = self.api_key
        if self.public_key:
            headers["public-key"] = self.public_key
        if self.secret_key:
            headers["secret-key"] = self.secret_key
        return headers

    def _http(self, method: str, path: str, payload: dict | None = None,
              query: dict | None = None) -> dict:
        url = f"{self.base}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query)

        body = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=body, method=method, headers=self._headers())

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return self._parse(resp.read(), resp.status)
        except urllib.error.HTTPError as err:
            try:
                return self._parse(err.read(), err.code)
            finally:
                err.close()
        except urllib.error.URLError as err:
            raise VtpassError("network", f"Could not reach VTpass: {err.reason}") from err

    @staticmethod
    def _parse(raw: bytes, http_status: int) -> dict:
        text = (raw or b"").decode("utf-8", "replace").strip()
        try:
            data = json.loads(text) if text else {}
        except json.JSONDecodeError:
            raise VtpassError(
                "invalid_response",
                f"VTpass returned non-JSON (HTTP {http_status})",
                http_status=http_status,
            )

        # The sandbox returns a bare JSON string on bad credentials.
        if not isinstance(data, dict):
            raise VtpassError(
                "invalid_credentials" if http_status in (401, 403) else "invalid_response",
                str(data),
                http_status=http_status,
            )

        if http_status in (401, 403):
            raise VtpassError(
                "invalid_credentials",
                data.get("response_description") or "Invalid Credentials.",
                http_status=http_status,
                raw=data,
            )
        return data

    # --- dry run -----------------------------------------------------------

    def _fixture(self, name: str) -> dict:
        path = FIXTURES / (self.fixture or name)
        if not path.exists():
            raise VtpassError("missing_fixture", f"No fixture at {path}")
        return json.loads(path.read_text())

    # --- endpoints ---------------------------------------------------------

    def list_variations(self, service_id: str = "ikeja-electric") -> list[dict]:
        """Meter types for a DISCO. Public endpoint — no credentials needed."""
        data = (self._fixture("service-variations_ikeja-electric.json") if self.dry_run
                else self._http("GET", "/service-variations", query={"serviceID": service_id}))

        content = data.get("content") or {}
        # VTpass misspells this as "varations" too; accept both.
        variations = content.get("variations") or content.get("varations") or []
        if not variations:
            raise VtpassError(
                "no_variations",
                f"VTpass returned no meter types for {service_id}",
                raw=data,
            )
        return variations

    def verify_meter(
        self,
        reference: str,
        *,
        service_id: str = "ikeja-electric",
        meter_type: str = "prepaid",
    ) -> dict:
        """Confirm a meter exists and return the customer name."""
        if self.dry_run:
            data = self._fixture("merchant-verify_ok.json")
        else:
            data = self._http(
                "POST",
                "/merchant-verify",
                {"billersCode": reference, "serviceID": service_id, "type": meter_type},
            )

        if data.get("code") != "000":
            raise VtpassError(
                str(data.get("code") or "unknown"),
                data.get("response_description") or "",
                raw=data,
            )

        content = data.get("content") or {}
        # VTpass returns code "000" even when it could not resolve the meter; the
        # failure is in the content body (captured live 2026-10-22). Trusting the
        # envelope alone would let a payment be attempted for a meter the vendor
        # has already said is wrong.
        if content.get("WrongBillersCode") is True or content.get("error"):
            raise VtpassError(
                "016",
                content.get("error") or "Invalid meter or phone number",
                raw=data,
            )
        return content

    def buy_electricity(
        self,
        reference: str,
        amount_ngn: int,
        phone: str,
        *,
        service_id: str = "ikeja-electric",
        meter_type: str = "prepaid",
        request_id: str | None = None,
    ) -> VendingResult:
        """Buy a prepaid token. Reuse `request_id` when retrying the same intent."""
        if amount_ngn < 500:
            raise ValueError("VTpass electricity minimum is 500 naira")
        return self.buy(
            service_id=service_id,
            reference=reference,
            amount_ngn=amount_ngn,
            phone=phone,
            variation_code=meter_type,
            request_id=request_id,
        )

    def buy(
        self,
        *,
        service_id: str,
        reference: str,
        amount_ngn: int,
        phone: str,
        variation_code: str | None = None,
        request_id: str | None = None,
    ) -> VendingResult:
        """Buy any product. Reuse `request_id` when retrying the same intent.

        - **airtime**: `variation_code` is omitted entirely — the service has no
          variations (`011 No Variations for MTN Airtime VTU`, captured live), so the
          amount is the product.
        - **data / TV**: `variation_code` is the plan, e.g. `mtn-100mb-1000`, `dstv79`.
        - **electricity**: `variation_code` is `prepaid`.
        """
        rid = request_id or new_request_id()
        payload = {
            "request_id": rid,
            "serviceID": service_id,
            "billersCode": reference,
            "amount": amount_ngn,
            "phone": phone,
        }
        if variation_code:
            payload["variation_code"] = variation_code

        data = (self._fixture("pay_ok.json") if self.dry_run
                else self._http("POST", "/pay", payload))

        code = str(data.get("code") or "unknown")
        txn = (data.get("content") or {}).get("transactions") or {}
        status = str(txn.get("status") or ("delivered" if code == "000" else "failed"))

        result = VendingResult(
            request_id=data.get("requestId") or rid,
            code=code,
            status=status,
            token=extract_token(data),
            # Electricity puts `units` at the top level; some products nest it.
            units=txn.get("units") or data.get("units"),
            amount_ngn=data.get("amount") or amount_ngn,
            description=data.get("response_description") or CODE_MESSAGES.get(code, ""),
            raw=data,
        )

        # A pending transaction is not an error — it may still deliver.
        if code != "000" and not result.pending:
            raise VtpassError(code, result.description, raw=data)

        return result

    def query_transaction(self, request_id: str) -> VendingResult:
        """Check a transaction that came back pending."""
        data = (self._fixture("pay_ok.json") if self.dry_run
                else self._http("POST", "/requery", {"request_id": request_id}))

        code = str(data.get("code") or "unknown")
        txn = (data.get("content") or {}).get("transactions") or {}
        return VendingResult(
            request_id=data.get("requestId") or request_id,
            code=code,
            status=str(txn.get("status") or "unknown"),
            token=extract_token(data),
            units=txn.get("units"),
            amount_ngn=data.get("amount"),
            description=data.get("response_description") or "",
            raw=data,
        )


# --- CLI --------------------------------------------------------------------

def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="VTpass client (dry-run by default)")
    parser.add_argument("--live", action="store_true", help="hit the real API (needs credentials)")
    parser.add_argument("--fixture", help="fixture filename to use in dry-run")

    # Repeat the global flags on each subcommand so they work either side of it.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--live", action="store_true", default=argparse.SUPPRESS,
                        help=argparse.SUPPRESS)
    common.add_argument("--fixture", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_var = sub.add_parser("variations", parents=[common], help="list meter types")
    p_var.add_argument("--service", default="ikeja-electric")

    p_verify = sub.add_parser("verify", parents=[common], help="verify a meter")
    p_verify.add_argument("--meter", required=True)
    p_verify.add_argument("--service", default="ikeja-electric")
    p_verify.add_argument("--type", default="prepaid")

    p_buy = sub.add_parser("buy", parents=[common], help="buy a token")
    p_buy.add_argument("--meter", required=True)
    p_buy.add_argument("--amount", type=int, required=True)
    p_buy.add_argument("--phone", required=True)
    p_buy.add_argument("--service", default="ikeja-electric")
    p_buy.add_argument("--type", default="prepaid")

    p_status = sub.add_parser("status", parents=[common], help="requery a transaction")
    p_status.add_argument("--request-id", required=True)

    args = parser.parse_args(argv)
    live = getattr(args, "live", False)
    fixture = getattr(args, "fixture", None)
    client = VtpassClient(dry_run=not live, fixture=fixture)

    mode = "LIVE" if live else "DRY-RUN"
    print(f"VTpass [{mode}] env={client.env} base={client.base}\n")

    try:
        if args.cmd == "variations":
            for v in client.list_variations(args.service):
                print(f"  {v['variation_code']:12} {v['name']}")

        elif args.cmd == "verify":
            info = client.verify_meter(args.meter, service_id=args.service,
                                       meter_type=args.type)
            print(json.dumps(info, indent=2))

        elif args.cmd == "buy":
            res = client.buy_electricity(args.meter, args.amount, args.phone,
                                         service_id=args.service, meter_type=args.type)
            print(f"  request_id  {res.request_id}")
            print(f"  code/status {res.code} / {res.status}")
            print(f"  units       {res.units}")
            print(f"  token       {res.token or '(none yet)'}")
            if res.delivered:
                print("\n  DELIVERED — safe to tell the user it's paid.")
            elif res.pending:
                print("\n  PENDING — do NOT claim success. Requery with the same request_id.")
            else:
                print("\n  NOT delivered — nothing was charged.")

        elif args.cmd == "status":
            res = client.query_transaction(args.request_id)
            print(f"  code/status {res.code} / {res.status}")
            print(f"  token       {res.token or '(none yet)'}")

    except VtpassError as err:
        print(f"FAILED  code={err.code}  retryable={err.retryable}")
        print(f"  {err.description}")
        print(f"  say to user: {err.user_message}")
        return 1
    except ValueError as err:
        print(f"INVALID INPUT  {err}")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
