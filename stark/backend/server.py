#!/usr/bin/env python3
"""Stark API stub — zero dependencies.

Purpose: hand the frontend a real HTTP server with the agreed shapes, before any
chain, bill-API, STT or LLM code exists. Nothing here is signed or charged.

Run it:      python3 server.py
Default:     http://127.0.0.1:8000
List routes: curl http://127.0.0.1:8000/

Mock values mirror the exported artboards (₦64,200 balance, ₦30,000 monthly cap,
Ikeja Electric "Home meter", DStv Compact, MTN airtime, "4 days left").
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

PORT = 8000
VERSION = "0.1.0-stub"

# --- mock data --------------------------------------------------------------

SAMPLE_TOKEN = "4821 0937 5512 8846 3019"
TARIFF_NGN_PER_KWH = 209.0
CAP_NGN = 30_000

BALANCE_NGN = 64_200
SPENT_NGN = 12_400
UNITS_LEFT = 11.4
DAYS_LEFT = 4


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ago(days: int = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


# Meter / phone / smartcard numbers are fake but shaped like the real thing.
BILLS: dict[str, dict[str, Any]] = {
    b["id"]: b
    for b in [
        {
            "id": "bill_home_meter",
            "kind": "electricity",
            "provider": "Ikeja Electric",
            "label": "Home meter",
            "reference": "04512345678",
            "last_amount_ngn": 5_000,
            "last_units": 23.9,
            "last_paid_at": ago(6),
        },
        {
            "id": "bill_dstv",
            "kind": "tv",
            "provider": "DStv",
            "label": "DStv Compact",
            "reference": "7032119456",
            "last_amount_ngn": 19_000,
            "last_units": None,
            "last_paid_at": ago(19),
        },
        {
            "id": "bill_airtime",
            "kind": "airtime",
            "provider": "MTN",
            "label": "My line",
            "reference": "08031234567",
            "last_amount_ngn": 1_000,
            "last_units": None,
            "last_paid_at": ago(2),
        },
    ]
}

ACTIVITY: list[dict[str, Any]] = [
    {
        "id": "rcpt_0003",
        "bill_id": "bill_home_meter",
        "bill_label": "Home meter",
        "amount_ngn": 5_000,
        "units": 23.9,
        "token": SAMPLE_TOKEN,
        "tx_hash": "8f2c1d4e6a9b0c3f5e7d1a2b4c6d8e0f1a3b5c7d9e0f2a4b6c8d0e1f3a5b7c9d",
        "created_at": ago(6),
    },
    {
        "id": "rcpt_0002",
        "bill_id": "bill_airtime",
        "bill_label": "My line",
        "amount_ngn": 1_000,
        "units": None,
        "token": None,
        "tx_hash": "1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f809",
        "created_at": ago(2),
    },
    {
        "id": "rcpt_0001",
        "bill_id": "bill_dstv",
        "bill_label": "DStv Compact",
        "amount_ngn": 19_000,
        "units": None,
        "token": None,
        "tx_hash": "9e8d7c6b5a49382716f5e4d3c2b1a09f8e7d6c5b4a39281706f5e4d3c2b1a09f",
        "created_at": ago(19),
    },
]

TELEMETRY: list[dict[str, Any]] = []

# Snapshot for the stub-only reset route, so tests and demos can rerun.
_INITIAL_BALANCE = BALANCE_NGN
_INITIAL_SPENT = SPENT_NGN
_INITIAL_ACTIVITY = [dict(r) for r in ACTIVITY]


# --- helpers ----------------------------------------------------------------


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, detail: dict | None = None):
        self.status = status
        self.body = {"code": code, "message": message, "detail": detail or {}}


def state() -> dict[str, Any]:
    return {
        "user_id": "user_tunde",
        "first_name": "Tunde",
        "currency": "NGN",
        "balance_ngn": BALANCE_NGN,
        "cap_ngn": CAP_NGN,
        "spent_ngn": SPENT_NGN,
        "remaining_cap_ngn": max(CAP_NGN - SPENT_NGN, 0),
        "units_left": UNITS_LEFT,
        "days_left": DAYS_LEFT,
        "bills": list(BILLS.values()),
        "as_of": now_iso(),
    }


def parse_form(raw: bytes, content_type: str) -> dict[str, str]:
    """Tolerate JSON, urlencoded or multipart so any client shape works."""
    ctype = (content_type or "").lower()
    if "application/json" in ctype:
        try:
            data = json.loads(raw or b"{}")
            return {k: str(v) for k, v in data.items()}
        except json.JSONDecodeError:
            return {}
    if "multipart/form-data" in ctype:
        fields: dict[str, str] = {}
        for m in re.finditer(
            rb'name="([^"]+)"(?:;\s*filename="[^"]*")?\r\n\r\n(.*?)\r\n--',
            raw,
            re.S,
        ):
            fields[m.group(1).decode()] = m.group(2).decode("utf-8", "replace")
        return fields
    return {k: v[0] for k, v in parse_qs((raw or b"").decode("utf-8", "replace")).items()}


# --- route handlers ---------------------------------------------------------


def h_index(_) -> tuple[int, dict]:
    return 200, {
        "service": "stark-api",
        "version": VERSION,
        "stub": True,
        "routes": sorted(f"{m} {p}" for m, p, _ in ROUTES),
    }


def h_health(_) -> tuple[int, dict]:
    return 200, {"status": "ok", "stub": True, "version": VERSION}


def h_state(_) -> tuple[int, dict]:
    return 200, state()


def h_bills(_) -> tuple[int, dict]:
    return 200, list(BILLS.values())


def h_bill(params) -> tuple[int, dict]:
    bill = BILLS.get(params["bill_id"])
    if bill is None:
        raise ApiError(404, "unknown_bill", f"No bill {params['bill_id']}")
    return 200, bill


def h_payment(body, _params=None) -> tuple[int, dict]:
    global BALANCE_NGN, SPENT_NGN

    bill_id = body.get("bill_id", "")
    try:
        amount = int(body.get("amount_ngn", 0))
    except (TypeError, ValueError):
        raise ApiError(400, "bad_amount", "amount_ngn must be an integer")

    bill = BILLS.get(bill_id)
    if bill is None:
        raise ApiError(404, "unknown_bill", f"No bill {bill_id}")
    if amount <= 0:
        raise ApiError(400, "bad_amount", "amount_ngn must be positive")

    # Mirrors the onchain policy check, so the UI can build these states today.
    if SPENT_NGN + amount > CAP_NGN:
        raise ApiError(
            409,
            "over_cap",
            "That would go over your monthly limit.",
            {
                "cap_ngn": CAP_NGN,
                "spent_ngn": SPENT_NGN,
                "remaining_ngn": max(CAP_NGN - SPENT_NGN, 0),
            },
        )
    if amount > BALANCE_NGN:
        raise ApiError(
            409,
            "insufficient_balance",
            "Not enough in your wallet. Add money first.",
            {"balance_ngn": BALANCE_NGN, "amount_ngn": amount},
        )

    units = None
    token = None
    if bill["kind"] == "electricity":
        units = round(amount / TARIFF_NGN_PER_KWH, 2)
        token = SAMPLE_TOKEN

    receipt = {
        "id": f"rcpt_{uuid.uuid4().hex[:6]}",
        "bill_id": bill["id"],
        "bill_label": bill["label"],
        "amount_ngn": amount,
        "units": units,
        "token": token,
        "tx_hash": uuid.uuid4().hex + uuid.uuid4().hex,
        "created_at": now_iso(),
    }
    ACTIVITY.insert(0, receipt)
    BALANCE_NGN -= amount
    SPENT_NGN += amount
    return 201, receipt


def h_activity(_) -> tuple[int, dict]:
    return 200, ACTIVITY[:20]


def h_suggestions(_) -> tuple[int, dict]:
    return 200, [
        {
            "id": "sug_units",
            "text": f"About {UNITS_LEFT:g} units left — roughly {DAYS_LEFT} days.",
            "severity": "warn",
            "reason": "units_low",
        },
        {
            "id": "sug_ac",
            "text": "Your AC is 78% of your usage this week.",
            "severity": "info",
            "reason": "load_imbalance",
        },
    ]


def h_telemetry(body) -> tuple[int, dict]:
    try:
        watts = float(body.get("watts", 0))
    except (TypeError, ValueError):
        raise ApiError(400, "bad_watts", "watts must be a number")
    TELEMETRY.append(
        {
            "device_id": body.get("device_id", "unknown"),
            "watts": watts,
            "ts": body.get("ts") or now_iso(),
        }
    )
    return 202, {"accepted": True, "count": len(TELEMETRY)}


def h_voice(body) -> tuple[int, dict]:
    """One shape for Telegram, the wall phone and any future speaker."""
    transcript = body.get("transcript_hint") or "hello stark what's my light bill"
    heard = transcript.lower()

    # The wake gate: no "stark", the client must stay silent.
    if "stark" not in heard:
        return 200, {"transcript": transcript, "ignored": True, "reply": None,
                     "token": None, "receipt_id": None}

    command = heard.split("stark", 1)[1].strip()

    # Word-boundary matching so "top it up", "top up" and "topup" all land.
    wants_query = re.search(r"\b(bill|bills|unit|units|balance|how much|spend|left)\b", command)
    wants_pay = re.search(r"\b(top\s?(it\s?)?up|topup|buy|pay|recharge|send)\b", command)

    if wants_query:
        reply = (
            f"You've got ₦{BALANCE_NGN:,} in your wallet and about {UNITS_LEFT:g} "
            f"units left — roughly {DAYS_LEFT} days at this rate."
        )
        return 200, {"transcript": transcript, "ignored": False, "reply": reply,
                     "token": None, "receipt_id": None}

    if wants_pay:
        reply = f"That's ₦5,000, under your ₦{CAP_NGN:,} cap. Paying now."
        return 200, {"transcript": transcript, "ignored": False, "reply": reply,
                     "token": SAMPLE_TOKEN,
                     "receipt_id": ACTIVITY[0]["id"] if ACTIVITY else None}

    return 200, {"transcript": transcript, "ignored": False,
                 "reply": "I can check your bill or top it up. Which one?",
                 "token": None, "receipt_id": None}


def h_reset(_body=None, _params=None) -> tuple[int, dict]:
    """Stub-only: restore the initial mock state so runs are repeatable."""
    global BALANCE_NGN, SPENT_NGN, ACTIVITY, TELEMETRY
    BALANCE_NGN = _INITIAL_BALANCE
    SPENT_NGN = _INITIAL_SPENT
    ACTIVITY = [dict(r) for r in _INITIAL_ACTIVITY]
    TELEMETRY = []
    return 200, {"reset": True}


def h_tg(body) -> tuple[int, dict]:
    # Real handler lands with the Telegram bot in M4.
    return 200, {"ok": True, "stub": True, "update_id": body.get("update_id")}


# (method, path regex, handler) — order matters, specific before generic.
ROUTES = [
    ("GET", r"^/$", h_index),
    ("GET", r"^/health$", h_health),
    ("GET", r"^/v1/state$", h_state),
    ("GET", r"^/v1/bills$", h_bills),
    ("GET", r"^/v1/bills/(?P<bill_id>[^/]+)$", h_bill),
    ("POST", r"^/v1/payments$", h_payment),
    ("GET", r"^/v1/activity$", h_activity),
    ("GET", r"^/v1/suggestions$", h_suggestions),
    ("POST", r"^/v1/telemetry$", h_telemetry),
    ("POST", r"^/v1/voice$", h_voice),
    ("POST", r"^/v1/tg/webhook$", h_tg),
    # Stub-only. Not part of the product contract; safe to ignore from the frontend.
    ("POST", r"^/v1/_stub/reset$", h_reset),
]


# --- HTTP plumbing ----------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    server_version = f"StarkStub/{VERSION}"

    def _cors(self) -> None:
        # Wide open locally so the frontend works from any dev port.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802 - required name
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""

        for route_method, pattern, handler in ROUTES:
            match = re.match(pattern, parsed.path)
            if not match or route_method != method:
                continue

            params = match.groupdict()
            try:
                if method == "GET":
                    status, payload = handler(params)
                else:
                    body = parse_form(raw, self.headers.get("Content-Type", ""))
                    if handler in (h_telemetry, h_tg):
                        status, payload = handler(body)
                    elif handler is h_payment:
                        status, payload = handler(body, params)
                    else:
                        status, payload = handler(body)
                self._send(status, payload)
            except ApiError as err:
                self._send(err.status, err.body)
            except Exception as err:  # keep the stub from dying mid-demo
                self._send(500, {"code": "stub_error", "message": str(err), "detail": {}})
            return

        self._send(404, {"code": "no_route", "message": f"No route {method} {parsed.path}",
                         "detail": {}})

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def log_message(self, fmt: str, *args) -> None:
        print(f"  {self.address_string()} {fmt % args}")


def main() -> None:
    print(f"Stark API stub {VERSION} — mock data only, nothing is charged.")
    print(f"  http://127.0.0.1:{PORT}/")
    print("  Ctrl-C to stop.\n")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
