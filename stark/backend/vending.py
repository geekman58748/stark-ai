"""Vending: turn a saved bill into the actual purchase.

Four product families are wired, all confirmed against `sandbox.vtpass.com` on
2026-10-22 and captured in `fixtures/` (see `catalog.py`):

| Kind | Vendor product | Shape |
|---|---|---|
| electricity | `ikeja-electric` / `prepaid` | amount |
| airtime | `mtn`, `airtel`, `glo`, `etisalat` | amount, bounded by the vendor's own min/max |
| data | `mtn-data`, `airtel-data`, `glo-data`, `etisalat-data` | **plan** |
| tv | `dstv`, `gotv`, `startimes`, `showmax` | **plan** |

The two shapes are not interchangeable. Airtime is a number of naira. Data and TV
are a *plan* with a fixed price — so the bill carries a `plan` (a VTpass variation
code like `dstv79`) and the requested amount must equal that plan's price. Paying
₦5,000 against a ₦7,900 bouquet is not a discount, it is a mispriced order.

Two rules come straight from `vtpass.py`:

1. **Delivered means `code == "000"` and `status == "delivered"`.** `099`/pending is
   not success, and the caller must not charge for it.
2. **A retry reuses its `request_id`.** The store finds the unfinished purchase and
   the gateway re-queries it rather than buying again.

Dry by default: the request still flows through the VTpass client, but it reads
`fixtures/pay_ok.json` instead of the network.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping

import vtpass
from catalog import AMOUNT, PLAN, CATALOG, Catalog, Product
from vtpass import VendingResult, VtpassClient, VtpassError

DELIVERED = "delivered"
PENDING = "pending"
FAILED = "failed"

# Electricity is not in the category fixtures: it is a single confirmed service.
ELECTRICITY_SERVICE = "ikeja-electric"
ELECTRICITY_MIN_NGN = 500

FALLBACK_PHONE = "08031234567"


@dataclass(frozen=True)
class ProductSpec:
    """What to call at VTpass, and how to check the amount before calling."""

    service_id: str
    variation_code: str | None
    mode: str
    token_required: bool = False
    min_ngn: int | None = None
    max_ngn: int | None = None
    plan_price_ngn: int | None = None


@dataclass(frozen=True)
class VendingOutcome:
    status: str
    token: str | None = None
    units: float | None = None
    vendor: str = "vtpass"
    code: str = ""
    message: str = ""
    token_required: bool = False

    @property
    def ok(self) -> bool:
        return self.status == DELIVERED


class VendingGateway:
    def __init__(
        self,
        client: VtpassClient | None = None,
        *,
        phone: str = FALLBACK_PHONE,
        tariff_ngn_per_kwh: float = 209.0,
        catalog: Catalog = CATALOG,
    ):
        self.client = client or VtpassClient(dry_run=True)
        self.phone = phone
        self.tariff = tariff_ngn_per_kwh
        self.catalog = catalog

    @property
    def live(self) -> bool:
        return not self.client.dry_run

    # --- resolution ----------------------------------------------------------

    def spec_for(self, bill: dict) -> tuple[ProductSpec | None, str]:
        """`(spec, refusal)`. Exactly one is meaningful."""
        kind = str(bill.get("kind") or "")
        if kind == "electricity":
            return (
                ProductSpec(
                    service_id=ELECTRICITY_SERVICE,
                    variation_code="prepaid",
                    mode=AMOUNT,
                    token_required=True,
                    min_ngn=ELECTRICITY_MIN_NGN,
                ),
                "",
            )

        product = self.catalog.product(kind, str(bill.get("provider") or ""))
        if product is None:
            return None, (
                f"I can't find {bill.get('provider') or 'that provider'} "
                f"for {kind or 'that'}. Nothing was charged."
            )
        return self._spec_from_product(bill, product)

    def _spec_from_product(
        self, bill: dict, product: Product
    ) -> tuple[ProductSpec | None, str]:
        if not product.needs_plan:
            return (
                ProductSpec(
                    service_id=product.service_id,
                    variation_code=None,
                    mode=AMOUNT,
                    min_ngn=product.min_ngn,
                    max_ngn=product.max_ngn,
                ),
                "",
            )

        code = str(bill.get("plan") or "")
        if not code:
            return None, (
                f"{bill.get('label') or 'That bill'} needs a plan chosen first. "
                "Nothing was charged."
            )

        plan = self.catalog.plan(product, code)
        if plan is None:
            return None, (
                f"I don't have a '{code}' plan for {product.name}. "
                "Nothing was charged."
            )
        return (
            ProductSpec(
                service_id=product.service_id,
                variation_code=plan.code,
                mode=PLAN,
                plan_price_ngn=plan.price_ngn,
            ),
            "",
        )

    # --- purchase ------------------------------------------------------------

    def buy(self, bill: dict, amount_ngn: int, request_id: str) -> VendingOutcome:
        """Buy for a bill. Never raises for a vendor or plan problem."""
        spec, refusal = self.spec_for(bill)
        if spec is None:
            return VendingOutcome(status=FAILED, vendor="none", message=refusal)

        problem = self._amount_problem(spec, amount_ngn)
        if problem:
            return VendingOutcome(
                status=FAILED, vendor="none", code=problem[0], message=problem[1]
            )

        try:
            result = self.client.buy(
                service_id=spec.service_id,
                reference=str(bill.get("reference") or ""),
                amount_ngn=amount_ngn,
                phone=self.phone,
                variation_code=spec.variation_code,
                request_id=request_id,
            )
        except VtpassError as err:
            return VendingOutcome(
                status=FAILED,
                code=str(err.code),
                message=err.user_message,
                token_required=spec.token_required,
            )

        return self._outcome(result, amount_ngn, spec)

    def requery(self, request_id: str, amount_ngn: int) -> VendingOutcome:
        """Ask the vendor about a purchase that came back pending."""
        try:
            result = self.client.query_transaction(request_id)
        except VtpassError as err:
            return VendingOutcome(status=PENDING, code=str(err.code),
                                  message=err.user_message)
        return self._outcome(result, amount_ngn, None)

    @staticmethod
    def _amount_problem(spec: ProductSpec, amount_ngn: int) -> tuple[str, str] | None:
        """Check the amount against the product *before* calling the vendor."""
        if spec.mode == PLAN:
            if amount_ngn != spec.plan_price_ngn:
                return (
                    "plan_price_mismatch",
                    f"That plan costs ₦{spec.plan_price_ngn:,}. "
                    "Nothing was charged.",
                )
            return None
        if spec.min_ngn is not None and amount_ngn < spec.min_ngn:
            return (
                "bad_amount",
                f"The least you can put on that is ₦{spec.min_ngn:,}. "
                "Nothing was charged.",
            )
        if spec.max_ngn is not None and amount_ngn > spec.max_ngn:
            return (
                "bad_amount",
                f"The most you can put on that is ₦{spec.max_ngn:,}. "
                "Nothing was charged.",
            )
        return None

    def _outcome(
        self, result: VendingResult, amount_ngn: int, spec: ProductSpec | None
    ) -> VendingOutcome:
        token_required = bool(spec and spec.token_required)

        if result.delivered:
            # Only electricity has a token and units. Reporting a 20-digit meter
            # token on an airtime purchase would be a lie with a number in it.
            token = _display_token(result.token) if token_required else None
            if token_required:
                units = (_derived_units(amount_ngn, self.tariff) if self.client.dry_run
                         else _units(result.units) or _derived_units(amount_ngn, self.tariff))
            else:
                units = None
            return VendingOutcome(
                status=DELIVERED,
                token=token,
                units=units,
                code=result.code,
                message=result.description,
                token_required=token_required,
            )

        if result.pending:
            return VendingOutcome(
                status=PENDING,
                code=result.code,
                message=result.description,
                token_required=token_required,
            )

        return VendingOutcome(
            status=FAILED,
            code=result.code,
            message=vtpass.CODE_MESSAGES.get(result.code, result.description),
            token_required=token_required,
        )


def _units(raw: object) -> float | None:
    try:
        return float(str(raw)) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _derived_units(amount_ngn: int, tariff: float) -> float | None:
    return round(amount_ngn / tariff, 2) if tariff > 0 else None


def _display_token(raw: str | None) -> str | None:
    """Group a 20-digit token in fours, the way it is printed and read aloud."""
    if not raw:
        return raw
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 20:
        return " ".join(digits[i:i + 4] for i in range(0, 20, 4))
    return raw


def gateway_from_env(
    env: Mapping[str, str] | None = None, *, default_phone: str | None = None
) -> VendingGateway:
    """Dry-run unless `STARK_VENDING=live`.

    Turning on live vending without credentials is a config error, not something to
    discover on the first customer's meter — so it fails here, at construction.
    """
    source = os.environ if env is None else env
    mode = (source.get("STARK_VENDING") or "dry").strip().lower()
    if mode not in ("dry", "live"):
        raise ValueError("STARK_VENDING must be dry or live")

    live = mode == "live"
    if live and not (
        (source.get("VTPASS_USERNAME") and source.get("VTPASS_PASSWORD"))
        or source.get("VTPASS_SECRET_KEY")
    ):
        raise ValueError(
            "STARK_VENDING=live needs VTPASS_USERNAME/VTPASS_PASSWORD "
            "(or the VTPASS_* key trio)"
        )

    return VendingGateway(
        VtpassClient(env=source.get("VTPASS_ENV"), dry_run=not live),
        phone=source.get("STARK_PHONE") or default_phone or FALLBACK_PHONE,
    )
