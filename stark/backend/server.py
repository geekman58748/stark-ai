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

import copy
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import agent as agent_layer
import catalog
import identities
import payments
import receipts
import telegram
import vault_signer
import vending

PORT = 8000
VERSION = "0.3.0-stub"

# --- mock data --------------------------------------------------------------

SAMPLE_TOKEN = "4821 0937 5512 8846 3019"
TARIFF_NGN_PER_KWH = 209.0
CAP_NGN = 30_000
BILL_KINDS = ("electricity", "airtime", "data", "tv", "internet", "water")
PLAN_KINDS = ("data", "tv")

SEED_BALANCE_NGN = 64_200
# The artboards' "Spent this month ₦23,000 of ₦30,000": three electricity
# top-ups (5,000 + 10,000 + 8,000). The airtime entry is an automatic top-up
# and the ₦20,000 entry is money in, so neither counts as bill spend.
SEED_SPENT_NGN = 23_000
SEED_UNITS_LEFT = 11.4
SEED_DAYS_LEFT = 4
UNITS_LEFT = SEED_UNITS_LEFT
DAYS_LEFT = SEED_DAYS_LEFT


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ago(days: int = 0, hours: int = 0, minutes: int = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days, hours=hours, minutes=minutes)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


# Meter / phone / smartcard numbers are fake but shaped like the real thing.
BILLS: dict[str, dict[str, Any]] = {
    b["id"]: b
    for b in [
        {
            "id": "bill_home_meter",
            "kind": "electricity",
            "provider": "Ikeja Electric",
            "label": "Home",
            "reference": "04512345678",
            "last_amount_ngn": 5_000,
            "last_units": 23.9,
            "last_paid_at": ago(0),
        },
        {
            "id": "bill_dstv",
            "kind": "tv",
            "provider": "DStv",
            "label": "Living room TV",
            "reference": "7032119456",
            # The plan is the product. `dstv79` is the Compact bouquet in VTpass's
            # captured catalogue and costs ₦7,900 — the artboard's ₦18,000 is a
            # different bouquet. See `catalog.py`.
            "plan": "dstv79",
            # No DStv payment in the seeded history: the artboards show it due
            # on Nov 3, not recently paid.
            "last_amount_ngn": None,
            "last_units": None,
            "last_paid_at": None,
        },
        {
            "id": "bill_airtime",
            "kind": "airtime",
            "provider": "MTN",
            "label": "My line",
            "reference": "08031234567",
            "last_amount_ngn": 1_000,
            "last_units": None,
            "last_paid_at": ago(0, hours=6),
        },
    ]
}

# Bills bought by plan carry the vendor's price, so the UI and the agent do not have
# to guess what a bouquet costs. Additive field on `Bill` (`docs/API.md`).
for _bill in BILLS.values():
    _product = catalog.CATALOG.product(_bill["kind"], _bill["provider"])
    if _product is not None and _product.needs_plan and _bill.get("plan"):
        _plan = catalog.CATALOG.plan(_product, _bill["plan"])
        if _plan is not None:
            _bill["plan_price_ngn"] = _plan.price_ngn

# Add/remove bill mutates `BILLS`; reset puts the artboards' three back.
SEED_BILLS = copy.deepcopy(BILLS)


def seed_receipts() -> list[dict[str, Any]]:
    """The six activity entries the artboards show. Rebuilt on every reset.

    The three delivered electricity top-ups total ₦23,000 — the artboard's "Spent
    this month". The ₦1,000 airtime entry is an automatic top-up and the ₦20,000
    entry is money in, so neither is bill spend; the ₦15,000 attempt was declined
    by the per-payment cap and was never charged.
    """
    return [
        {
            "id": "rcpt_0003",
            "request_id": "seed-0003",
            "bill_id": "bill_home_meter",
            "bill_label": "Home electricity",
            "meter": BILLS["bill_home_meter"]["reference"],
            "amount_ngn": 5_000,
            "units": 23.9,
            "token": SAMPLE_TOKEN,
            "tx_hash": "8f2c1d4e6a9b0c3f5e7d1a2b4c6d8e0f1a3b5c7d9e0f2a4b6c8d0e1f3a5b7c9d",
            "status": "delivered",
            "entry_type": "bill",
            "source": "Telegram voice note",
            "vendor": "seed",
            "vendor_code": "000",
            "vendor_message": "seeded",
            "created_at": ago(0),
        },
        {
            "id": "rcpt_0004",
            "request_id": "seed-0004",
            "bill_id": "bill_home_meter",
            "bill_label": "Home electricity",
            "meter": BILLS["bill_home_meter"]["reference"],
            "amount_ngn": 15_000,
            "units": None,
            "token": None,
            "tx_hash": None,
            "status": "declined",
            "entry_type": "bill",
            "source": "Telegram voice note",
            "vendor": "policy",
            "vendor_code": "over_per_payment_cap",
            "vendor_message": "Over your ₦10,000 per-payment limit",
            "created_at": ago(0, minutes=1),
        },
        {
            "id": "rcpt_0002",
            "request_id": "seed-0002",
            "bill_id": "bill_airtime",
            "bill_label": "My line airtime",
            "meter": BILLS["bill_airtime"]["reference"],
            "amount_ngn": 1_000,
            "units": None,
            "token": None,
            "tx_hash": None,
            "status": "delivered",
            "entry_type": "autotopup",
            "source": "Automatic top-up",
            "vendor": "seed",
            "vendor_code": "000",
            "vendor_message": "seeded",
            "created_at": ago(0, hours=6),
        },
        {
            "id": "rcpt_0005",
            "request_id": "seed-0005",
            "bill_id": "wallet",
            "bill_label": "Added money",
            "meter": None,
            "amount_ngn": 20_000,
            "units": None,
            "token": None,
            "tx_hash": None,
            "status": "received",
            "entry_type": "deposit",
            "source": "Bank transfer",
            "vendor": "seed",
            "vendor_code": "000",
            "vendor_message": "seeded",
            "created_at": ago(10),
        },
        {
            "id": "rcpt_0006",
            "request_id": "seed-0006",
            "bill_id": "bill_home_meter",
            "bill_label": "Home electricity",
            "meter": BILLS["bill_home_meter"]["reference"],
            "amount_ngn": 10_000,
            "units": 47.8,
            "token": "1290 4478 0031 6652 9917",
            "tx_hash": None,
            "status": "delivered",
            "entry_type": "bill",
            "source": "Wall phone",
            "vendor": "seed",
            "vendor_code": "000",
            "vendor_message": "seeded",
            "created_at": ago(14),
        },
        {
            "id": "rcpt_0001",
            "request_id": "seed-0001",
            "bill_id": "bill_home_meter",
            "bill_label": "Home electricity",
            "meter": BILLS["bill_home_meter"]["reference"],
            "amount_ngn": 8_000,
            "units": 38.3,
            "token": "6634 2210 9845 1176 0042",
            "tx_hash": None,
            "status": "delivered",
            "entry_type": "bill",
            "source": "Typed on Telegram",
            "vendor": "seed",
            "vendor_code": "000",
            "vendor_message": "seeded",
            "created_at": ago(20),
        },
    ]


def sync_bill_history(history: list[dict[str, Any]]) -> None:
    """Point each bill at its newest delivered payment in the seeded history."""
    newest: dict[str, dict[str, Any]] = {}
    for entry in history:
        if (entry.get("entry_type") in ("bill", "autotopup")
                and entry.get("status") == "delivered"
                and entry.get("bill_id") in BILLS):
            newest.setdefault(entry["bill_id"], entry)
    for bill_id, bill in BILLS.items():
        entry = newest.get(bill_id)
        if entry is not None:
            bill["last_amount_ngn"] = entry["amount_ngn"]
            bill["last_units"] = entry["units"]
            bill["last_paid_at"] = entry["created_at"]

# The owner's limits, mirrored from the vault's `get_policy()`. The agent enforces
# these before anything is signed; the contract enforces them again onchain.
#
# ₦10,000, not the ₦5,000 the first draft used: a DStv Compact bouquet is ₦7,900 in
# VTpass's catalogue, so a ₦5,000 per-payment cap would make the TV bill impossible
# to pay. The monthly cap is what does the real work.
PER_PAYMENT_CAP_NGN = 10_000
LIMITS = agent_layer.Limits(
    monthly_cap_ngn=CAP_NGN,
    per_payment_cap_ngn=PER_PAYMENT_CAP_NGN,
    allowed_meters=frozenset(b["reference"] for b in BILLS.values()),
)

TELEMETRY: list[dict[str, Any]] = []

# Persistence: receipts and the wallet live in SQLite, so a restart keeps history
# and balance in agreement. `stark.db` is gitignored.
STORE = receipts.ReceiptStore()
PAYMENTS = payments.PaymentService(STORE, vending.gateway_from_env(
    default_phone=BILLS["bill_airtime"]["reference"]
))

if STORE.wallet() is None:
    _seed = seed_receipts()
    STORE.replace_all(_seed, balance_ngn=SEED_BALANCE_NGN, spent_ngn=SEED_SPENT_NGN)
    sync_bill_history(_seed)


# --- helpers ----------------------------------------------------------------


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, detail: dict | None = None):
        self.status = status
        self.body = {"code": code, "message": message, "detail": detail or {}}


def state() -> dict[str, Any]:
    wallet = STORE.wallet() or {"balance_ngn": SEED_BALANCE_NGN, "spent_ngn": SEED_SPENT_NGN}
    balance, spent = wallet["balance_ngn"], wallet["spent_ngn"]
    has_electricity = any(b["kind"] == "electricity" for b in BILLS.values())
    return {
        "user_id": "user_tunde",
        "first_name": "Tunde",
        "currency": "NGN",
        "balance_ngn": balance,
        "cap_ngn": LIMITS.monthly_cap_ngn,
        "spent_ngn": spent,
        "remaining_cap_ngn": max(LIMITS.monthly_cap_ngn - spent, 0),
        "units_left": UNITS_LEFT if has_electricity else None,
        "days_left": DAYS_LEFT if has_electricity else None,
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


def h_plans(params) -> tuple[int, dict]:
    """Every priced plan for data and TV, straight from the captured catalogue."""
    kind = str(params.get("kind") or "").strip().lower()
    provider = str(params.get("provider") or "").strip()
    if kind and kind not in PLAN_KINDS:
        raise ApiError(400, "bad_kind", "Plans exist only for data and TV.")
    wanted = _slug(provider)
    rows: list[dict[str, Any]] = []
    for each_kind in ([kind] if kind else list(PLAN_KINDS)):
        for service in catalog.CATALOG.services(each_kind):
            service_id = str(service.get("serviceID") or "")
            name = str(service.get("name") or service_id)
            # Loosely: "mtn" must find "mtn-data", the way a picker's provider
            # chip does. Exact matching here returned an empty list for the very
            # example in docs/API.md.
            if wanted and not any(
                wanted in slug for slug in (_slug(service_id), _slug(name))
            ):
                continue
            product = catalog.CATALOG.product(each_kind, service_id)
            if product is None or not product.needs_plan:
                continue
            for plan in catalog.CATALOG.plans(product):
                rows.append({
                    "kind": each_kind,
                    "provider": service_id,
                    "service_name": name,
                    "plan": plan.code,
                    "label": plan.name,
                    "price_ngn": plan.price_ngn,
                })
    rows.sort(key=lambda row: (row["kind"], row["provider"], row["price_ngn"]))
    return 200, rows


def h_bill_add(body) -> tuple[int, dict]:
    kind = str(body.get("kind") or "").strip().lower()
    if kind not in BILL_KINDS:
        raise ApiError(400, "bad_kind", f"kind must be one of {', '.join(BILL_KINDS)}")
    provider = str(body.get("provider") or "").strip()
    if not provider:
        raise ApiError(400, "bad_bill", "provider is required")
    reference = re.sub(r"\s+", "", str(body.get("reference") or ""))
    if not 4 <= len(reference) <= 32:
        raise ApiError(400, "bad_reference", "reference must be 4–32 characters")
    label = str(body.get("label") or "").strip() or provider
    plan = str(body.get("plan") or "").strip() or None
    plan_price: int | None = None

    if kind == "electricity":
        # Only Ikeja is confirmed. Pretending another DISCO works would vend on
        # Ikeja's service id, which is the kind of silent lie this repo avoids.
        if _slug(provider) not in ("ikeja", "ikejaelectric"):
            raise ApiError(
                400, "unsupported_product",
                "Only Ikeja Electric is confirmed for electricity.",
            )
        plan = None
    elif kind in ("airtime", "data", "tv"):
        product = catalog.CATALOG.product(kind, provider)
        if product is None:
            raise ApiError(400, "unsupported_product",
                           f"I can't find {provider} for {kind}.")
        if product.needs_plan:
            if not plan:
                raise ApiError(400, "plan_required", "Choose a plan first.")
            chosen = catalog.CATALOG.plan(product, plan)
            if chosen is None:
                raise ApiError(400, "unknown_plan",
                               f"No '{plan}' plan for {product.name}.")
            plan_price = chosen.price_ngn
        else:
            plan = None
    else:
        # Internet and water have no confirmed VTpass product yet; the bill can be
        # saved, but paying it will refuse and charge nothing.
        plan = None

    if any(b["kind"] == kind and b["reference"] == reference
           for b in BILLS.values()):
        raise ApiError(409, "duplicate_bill", "That bill is already saved.")

    bill: dict[str, Any] = {
        "id": f"bill_{uuid.uuid4().hex[:8]}",
        "kind": kind,
        "provider": provider,
        "label": label,
        "reference": reference,
        "last_amount_ngn": None,
        "last_units": None,
        "last_paid_at": None,
    }
    if plan:
        bill["plan"] = plan
    if plan_price is not None:
        bill["plan_price_ngn"] = plan_price
    BILLS[bill["id"]] = bill
    _rebuild_limits()
    return 201, bill


def h_bill_update(body, params) -> tuple[int, dict]:
    bill = BILLS.get(params["bill_id"])
    if bill is None:
        raise ApiError(404, "unknown_bill", f"No bill {params['bill_id']}")
    if "label" in body:
        label = str(body.get("label") or "").strip()
        if not label:
            raise ApiError(400, "bad_bill", "label cannot be empty")
        bill["label"] = label
    if "plan" in body:
        if bill["kind"] not in PLAN_KINDS:
            raise ApiError(400, "bad_bill", "Only data and TV bills have plans.")
        product = catalog.CATALOG.product(bill["kind"], bill["provider"])
        if product is None:
            raise ApiError(400, "unsupported_product", "That provider has no plans.")
        code = str(body.get("plan") or "").strip()
        chosen = catalog.CATALOG.plan(product, code) if code else None
        if chosen is None:
            raise ApiError(400, "unknown_plan", f"No '{code}' plan for {product.name}.")
        bill["plan"] = chosen.code
        bill["plan_price_ngn"] = chosen.price_ngn
    return 200, bill


def h_bill_delete(params) -> tuple[int, dict]:
    global UNITS_LEFT
    bill_id = params["bill_id"]
    if bill_id not in BILLS:
        raise ApiError(404, "unknown_bill", f"No bill {bill_id}")
    if STORE.has_pending(bill_id):
        raise ApiError(409, "bill_in_flight",
                       "That bill has a payment still in flight. Try again after it settles.")
    del BILLS[bill_id]
    if not any(b["kind"] == "electricity" for b in BILLS.values()):
        UNITS_LEFT = 0.0
    _rebuild_limits()
    return 200, {"deleted": True, "bill_id": bill_id}


def _apply_delivery_to_state(receipt: dict[str, Any]) -> None:
    """Keep the bill and the live unit count in step with a delivered payment.

    `spent_ngn` is moved by the store; this is the part a user sees on the
    dashboard — the bill's last top-up and the units it bought.
    """
    global UNITS_LEFT
    bill = BILLS.get(receipt.get("bill_id"))
    if bill is None:
        return
    bill["last_amount_ngn"] = receipt["amount_ngn"]
    bill["last_units"] = receipt.get("units")
    bill["last_paid_at"] = receipt["created_at"]
    units = receipt.get("units")
    if units is not None and bill.get("kind") == "electricity":
        UNITS_LEFT = round(UNITS_LEFT + float(units), 2)


def book_payment(bill_id: str, amount: int, tx_hash: str | None = None) -> dict:
    """Validate and buy. Shared by the REST route and the agent.

    Validation is the contract's (404/400/409). The purchase and the charging happen
    in `payments.PaymentService`, which records the intent before it calls the
    vendor and only charges once the vendor has delivered.
    """
    bill = BILLS.get(bill_id)
    if bill is None:
        raise ApiError(404, "unknown_bill", f"No bill {bill_id}")
    if amount <= 0:
        raise ApiError(400, "bad_amount", "amount_ngn must be positive")

    wallet = STORE.wallet() or {
        "balance_ngn": SEED_BALANCE_NGN,
        "spent_ngn": SEED_SPENT_NGN,
    }
    spent, balance = wallet["spent_ngn"], wallet["balance_ngn"]

    # Mirrors the onchain policy check, so the UI can build these states today.
    if amount > LIMITS.per_payment_cap_ngn:
        raise ApiError(
            409,
            "over_per_payment_cap",
            "That's over the most you allow in one go.",
            {"amount_ngn": amount, "cap_ngn": LIMITS.per_payment_cap_ngn},
        )
    if spent + amount > LIMITS.monthly_cap_ngn:
        raise ApiError(
            409,
            "over_cap",
            "That would go over your monthly limit.",
            {
                "cap_ngn": LIMITS.monthly_cap_ngn,
                "spent_ngn": spent,
                "remaining_ngn": max(LIMITS.monthly_cap_ngn - spent, 0),
            },
        )
    if amount > balance:
        raise ApiError(
            409,
            "insufficient_balance",
            "Not enough in your wallet. Add money first.",
            {"balance_ngn": balance, "amount_ngn": amount},
        )

    try:
        receipt = PAYMENTS.pay(bill, amount, tx_hash=tx_hash)
    except payments.SpendError as err:
        status = 409 if err.code == payments.INSUFFICIENT_BALANCE else 502
        raise ApiError(status, err.code, err.message, err.detail) from err

    if receipt.get("status") == "delivered":
        _apply_delivery_to_state(receipt)

    return receipts.api_shape(receipt)


def h_payment(body, _params=None) -> tuple[int, dict]:
    bill_id = body.get("bill_id", "")
    try:
        amount = int(body.get("amount_ngn", 0))
    except (TypeError, ValueError):
        raise ApiError(400, "bad_amount", "amount_ngn must be an integer")
    return 201, book_payment(bill_id, amount)


class ServerToolbox:
    """The agent's view of this server's in-memory state.

    Deliberately thin: the agent may read state and pay a bill, and nothing else.
    """

    def get_state(self) -> dict:
        return state()

    def list_bills(self) -> list[dict]:
        return list(BILLS.values())

    def recent_activity(self) -> list[dict]:
        return PAYMENTS.recent(20)

    def pay(self, bill_id: str, amount_ngn: int) -> dict:
        try:
            return book_payment(bill_id, amount_ngn)
        except ApiError as err:
            raise agent_layer.PaymentError(
                err.body["code"], err.body["message"], err.body["detail"]
            ) from err


# No key configured → the agent answers without signing, like the rest of the stub.
AGENT = agent_layer.build_agent(
    ServerToolbox(), LIMITS, signer=vault_signer.signer_from_env()
)

# M4: the Telegram door. Same database as the receipts. Refuses every update
# until TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET are set (fail closed).
TG_ADAPTER = telegram.TelegramAdapter(
    agent=AGENT,
    identities=identities.IdentityStore(STORE.path),
    bot_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
    secret=os.environ.get("TELEGRAM_WEBHOOK_SECRET"),
    owner_user_id=os.environ.get("STARK_TG_OWNER_ID", "user_tunde"),
    log=lambda line: print(f"  [tg] {line}"),
)


def _limits_payload() -> dict[str, Any]:
    wallet = STORE.wallet() or {"balance_ngn": SEED_BALANCE_NGN, "spent_ngn": SEED_SPENT_NGN}
    spent = wallet["spent_ngn"]
    return {
        "monthly_cap_ngn": LIMITS.monthly_cap_ngn,
        "per_payment_cap_ngn": LIMITS.per_payment_cap_ngn,
        "spent_ngn": spent,
        "remaining_cap_ngn": max(LIMITS.monthly_cap_ngn - spent, 0),
    }


def _wallet_payload() -> dict[str, Any]:
    wallet = STORE.wallet() or {"balance_ngn": SEED_BALANCE_NGN, "spent_ngn": SEED_SPENT_NGN}
    return {
        "currency": "NGN",
        "balance_ngn": wallet["balance_ngn"],
        "spent_ngn": wallet["spent_ngn"],
        "monthly_cap_ngn": LIMITS.monthly_cap_ngn,
        "remaining_cap_ngn": max(LIMITS.monthly_cap_ngn - wallet["spent_ngn"], 0),
        "added_this_month_ngn": STORE.added_this_month(),
    }


def _rebuild_limits(*, monthly_cap_ngn: int | None = None,
                    per_payment_cap_ngn: int | None = None,
                    meters=None) -> None:
    """Replace the frozen Limits object and the agent's copy of it."""
    global LIMITS
    LIMITS = agent_layer.Limits(
        monthly_cap_ngn=LIMITS.monthly_cap_ngn if monthly_cap_ngn is None else monthly_cap_ngn,
        per_payment_cap_ngn=(
            LIMITS.per_payment_cap_ngn if per_payment_cap_ngn is None
            else per_payment_cap_ngn
        ),
        allowed_meters=frozenset(
            str(m) for m in (
                meters if meters is not None
                else (b["reference"] for b in BILLS.values())
            ) if m
        ),
    )
    AGENT.limits = LIMITS


def _int_field(body: dict[str, Any], name: str, code: str = "bad_amount") -> int:
    try:
        return int(body.get(name, ""))
    except (TypeError, ValueError):
        raise ApiError(400, code, f"{name} must be an integer") from None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def h_activity(_) -> tuple[int, dict]:
    return 200, PAYMENTS.recent(20)


def h_limits(_params=None) -> tuple[int, dict]:
    return 200, _limits_payload()


def h_limits_patch(body) -> tuple[int, dict]:
    monthly_raw = body.get("monthly_cap_ngn")
    per_raw = body.get("per_payment_cap_ngn")
    monthly = (_int_field(body, "monthly_cap_ngn", "bad_limits")
               if monthly_raw not in (None, "") else None)
    per = (_int_field(body, "per_payment_cap_ngn", "bad_limits")
           if per_raw not in (None, "") else None)
    if monthly is not None and monthly <= 0:
        raise ApiError(400, "bad_limits", "monthly_cap_ngn must be positive")
    if per is not None and per <= 0:
        raise ApiError(400, "bad_limits", "per_payment_cap_ngn must be positive")
    effective_monthly = LIMITS.monthly_cap_ngn if monthly is None else monthly
    effective_per = LIMITS.per_payment_cap_ngn if per is None else per
    if effective_per > effective_monthly:
        raise ApiError(400, "bad_limits",
                       "The per-payment limit can't exceed the monthly limit.")
    _rebuild_limits(monthly_cap_ngn=monthly, per_payment_cap_ngn=per)
    return 200, _limits_payload()


def h_wallet(_params=None) -> tuple[int, dict]:
    return 200, _wallet_payload()


def h_wallet_topup(body) -> tuple[int, dict]:
    amount = _int_field(body, "amount_ngn")
    if amount <= 0:
        raise ApiError(400, "bad_amount", "amount_ngn must be positive")
    request_id = str(body.get("request_id") or f"dep_{uuid.uuid4().hex[:12]}")
    existing = STORE.by_request_id(request_id)
    if existing is not None:
        return 200, {"wallet": _wallet_payload(), "entry": receipts.api_shape(existing)}
    entry, _ = STORE.record_deposit({
        "id": f"rcpt_{uuid.uuid4().hex[:6]}",
        "request_id": request_id,
        "bill_id": "wallet",
        "bill_label": "Added money",
        "meter": None,
        "amount_ngn": amount,
        "units": None,
        "token": None,
        "tx_hash": None,
        "status": "received",
        "entry_type": "deposit",
        "source": str(body.get("source") or "Bank transfer")[:40],
        "vendor": "ledger",
        "vendor_code": "000",
        "vendor_message": "deposit",
        "created_at": now_iso(),
    }, amount)
    return 201, {"wallet": _wallet_payload(), "entry": receipts.api_shape(entry)}


def h_wallet_withdraw(body) -> tuple[int, dict]:
    amount = _int_field(body, "amount_ngn")
    if amount <= 0:
        raise ApiError(400, "bad_amount", "amount_ngn must be positive")
    request_id = str(body.get("request_id") or f"wd_{uuid.uuid4().hex[:12]}")
    existing = STORE.by_request_id(request_id)
    if existing is not None:
        return 200, {"wallet": _wallet_payload(), "entry": receipts.api_shape(existing)}
    try:
        entry, _ = STORE.record_withdrawal({
            "id": f"rcpt_{uuid.uuid4().hex[:6]}",
            "request_id": request_id,
            "bill_id": "wallet",
            "bill_label": "Withdrawal",
            "meter": None,
            "amount_ngn": amount,
            "units": None,
            "token": None,
            "tx_hash": None,
            "status": "sent",
            "entry_type": "withdrawal",
            "source": "To your bank",
            "vendor": "ledger",
            "vendor_code": "000",
            "vendor_message": "withdrawal",
            "created_at": now_iso(),
        }, amount)
    except ValueError:
        wallet = STORE.wallet() or {"balance_ngn": 0, "spent_ngn": 0}
        raise ApiError(
            409, "insufficient_balance", "Not enough in your wallet.",
            {"balance_ngn": wallet["balance_ngn"], "amount_ngn": amount},
        ) from None
    return 201, {"wallet": _wallet_payload(), "entry": receipts.api_shape(entry)}


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
    """One shape for Telegram, the wall phone and any future speaker.

    The wake gate stays here, in front of the agent, so Telegram and the phone
    share one implementation. Everything past it is M2: the model picks tools,
    the policy gate decides, and `reply` comes back already speakable.
    """
    transcript = body.get("transcript_hint") or "hello stark what's my light bill"

    if "stark" not in transcript.lower():
        return 200, {"transcript": transcript, "ignored": True, "reply": None,
                     "token": None, "receipt_id": None}

    return 200, AGENT.respond(transcript).as_voice_payload(transcript)


def h_reset(_body=None, _params=None) -> tuple[int, dict]:
    """Stub-only: restore the seeded state so runs are repeatable.

    This wipes the receipt store and re-seeds it, so a demo starts from the
    artboards' numbers every time.
    """
    global TELEMETRY, UNITS_LEFT
    BILLS.clear()
    BILLS.update(copy.deepcopy(SEED_BILLS))
    history = seed_receipts()
    STORE.replace_all(
        history, balance_ngn=SEED_BALANCE_NGN, spent_ngn=SEED_SPENT_NGN
    )
    sync_bill_history(history)
    _rebuild_limits(monthly_cap_ngn=CAP_NGN, per_payment_cap_ngn=PER_PAYMENT_CAP_NGN)
    UNITS_LEFT = SEED_UNITS_LEFT
    TELEMETRY = []
    TG_ADAPTER.identities.clear()
    return 200, {"reset": True}


def h_tg(raw: bytes, headers) -> tuple[int, dict]:
    """Telegram webhook. Verifies before parsing, per HANDOFF §8A.

    The raw body matters: Telegram posts JSON, and the signature check must run
    on exactly what was sent, before any parsing of it.
    """
    try:
        TG_ADAPTER.verify_secret(headers.get("X-Telegram-Bot-Api-Secret-Token"))
    except telegram.TelegramError as err:
        return err.status, {"code": err.code, "message": err.message, "detail": {}}

    try:
        update = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return 400, {"code": "bad_update", "message": "Body is not JSON.", "detail": {}}
    return 200, TG_ADAPTER.handle_update(update)


# (method, path regex, handler) — order matters, specific before generic.
ROUTES = [
    ("GET", r"^/$", h_index),
    ("GET", r"^/health$", h_health),
    ("GET", r"^/v1/state$", h_state),
    ("GET", r"^/v1/bills$", h_bills),
    ("POST", r"^/v1/bills$", h_bill_add),
    ("GET", r"^/v1/bills/(?P<bill_id>[^/]+)$", h_bill),
    ("PATCH", r"^/v1/bills/(?P<bill_id>[^/]+)$", h_bill_update),
    ("DELETE", r"^/v1/bills/(?P<bill_id>[^/]+)$", h_bill_delete),
    ("GET", r"^/v1/plans$", h_plans),
    ("POST", r"^/v1/payments$", h_payment),
    ("GET", r"^/v1/activity$", h_activity),
    ("GET", r"^/v1/limits$", h_limits),
    ("PATCH", r"^/v1/limits$", h_limits_patch),
    ("GET", r"^/v1/wallet$", h_wallet),
    ("POST", r"^/v1/wallet/topup$", h_wallet_topup),
    ("POST", r"^/v1/wallet/withdraw$", h_wallet_withdraw),
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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
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
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        for route_method, pattern, handler in ROUTES:
            match = re.match(pattern, parsed.path)
            if not match or route_method != method:
                continue

            params = {**query, **match.groupdict()}
            try:
                if method == "GET":
                    status, payload = handler(params)
                elif method == "DELETE":
                    status, payload = handler(params)
                else:
                    body = parse_form(raw, self.headers.get("Content-Type", ""))
                    if handler is h_tg:
                        status, payload = handler(raw, self.headers)
                    elif handler is h_telemetry:
                        status, payload = handler(body)
                    elif handler in (h_payment, h_bill_update):
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

    def do_PATCH(self) -> None:  # noqa: N802
        self._dispatch("PATCH")

    def do_DELETE(self) -> None:  # noqa: N802
        self._dispatch("DELETE")

    def log_message(self, fmt: str, *args) -> None:
        print(f"  {self.address_string()} {fmt % args}")


def main() -> None:
    print(f"Stark API stub {VERSION} — mock data only, nothing is charged.")
    print(f"  http://127.0.0.1:{PORT}/")
    print("  Ctrl-C to stop.\n")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
