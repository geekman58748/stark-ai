"""Which VTpass product a bill actually is — read from captured fixtures.

Nothing here is guessed. Every service id, product type and price in this module
comes from a response captured off `sandbox.vtpass.com` on 2026-10-22 and stored in
`fixtures/`:

| Fixture | What it proves |
|---|---|
| `services_airtime.json` | `mtn`, `airtel`, `glo`, `etisalat`; all `product_type: flexible` |
| `services_data.json` | `mtn-data`, `airtel-data`, `glo-data`, `etisalat-data`; all `fix` |
| `services_tv-subscription.json` | `dstv`, `gotv`, `startimes`, `showmax` |
| `service-variations_{...}.json` | the plans and their prices |
| `service-variations_mtn.json` | `011 No Variations for MTN Airtime VTU` — airtime is billed by amount, not a plan |

Two product shapes fall out of that:

- **flexible** (airtime, and electricity): the amount is the product. Validate it
  against the vendor's own `minimium_amount`/`maximum_amount`.
- **fix** (data, DStv, GOtv, Showmax): the *plan* is the product and the price is the
  plan's. A bill therefore needs a `plan` (a variation code) and the requested amount
  must equal that plan's price — otherwise the vendor charges something the user did
  not ask for.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"

CATEGORY_FILES = {
    "airtime": "services_airtime.json",
    "data": "services_data.json",
    "tv": "services_tv-subscription.json",
}

AMOUNT = "amount"
PLAN = "plan"


@dataclass(frozen=True)
class Product:
    kind: str
    service_id: str
    name: str
    mode: str  # AMOUNT | PLAN
    min_ngn: int | None = None
    max_ngn: int | None = None

    @property
    def needs_plan(self) -> bool:
        return self.mode == PLAN


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    price_ngn: int


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _money(raw: object) -> int | None:
    try:
        return int(Decimal(str(raw)))
    except (InvalidOperation, TypeError, ValueError):
        return None


class Catalog:
    def __init__(self, fixtures: Path = FIXTURES):
        self.fixtures = fixtures
        self._services: dict[str, list[dict]] = {}
        self._plans: dict[str, list[Plan]] = {}

    # --- services ------------------------------------------------------------

    def services(self, kind: str) -> list[dict]:
        if kind not in self._services:
            data = _load_fixtures(self.fixtures, CATEGORY_FILES.get(kind, ""))
            content = data.get("content")
            self._services[kind] = content if isinstance(content, list) else []
        return self._services[kind]

    def product(self, kind: str, provider: str) -> Product | None:
        """The vendor product for a bill kind and provider, or `None`."""
        wanted = slug(provider)
        if not wanted:
            return None

        best: tuple[int, dict] | None = None
        for service in self.services(kind):
            score = _match_score(wanted, service)
            if score and (best is None or score > best[0]):
                best = (score, service)
        if best is None:
            return None

        service = best[1]
        service_id = str(service.get("serviceID", ""))
        # The plan list decides the shape, not the `product_type` field: VTpass marks
        # Startimes "flexible" and still sells it as 25 priced bouquets. If the vendor
        # publishes plans, the plan is the product.
        return Product(
            kind=kind,
            service_id=service_id,
            name=str(service.get("name", "")),
            mode=PLAN if self.plans_for(service_id) else AMOUNT,
            min_ngn=_money(service.get("minimium_amount")),
            max_ngn=_money(service.get("maximum_amount")),
        )

    # --- plans ---------------------------------------------------------------

    def plans_for(self, service_id: str) -> list[Plan]:
        if service_id not in self._plans:
            data = _load_fixtures(
                self.fixtures, f"service-variations_{service_id}.json"
            )
            content = data.get("content") or {}
            raw = []
            if isinstance(content, dict):
                # VTpass misspells this as "varations" in some responses.
                raw = content.get("variations") or content.get("varations") or []
            plans = []
            for item in raw if isinstance(raw, list) else []:
                price = _money(item.get("variation_amount"))
                code = str(item.get("variation_code") or "")
                if code and price is not None:
                    plans.append(Plan(code=code, name=str(item.get("name") or code),
                                      price_ngn=price))
            self._plans[service_id] = plans
        return self._plans[service_id]

    def plans(self, product: Product) -> list[Plan]:
        return self.plans_for(product.service_id)

    def plan(self, product: Product, code: str) -> Plan | None:
        return next((p for p in self.plans(product) if p.code == code), None)


def _match_score(wanted: str, service: dict) -> int:
    """How well a bill's provider names this VTpass service.

    Higher wins. The ordering matters: `glo` must pick `glo-data`, not `glo-sme-data`.
    """
    service_id = slug(str(service.get("serviceID", "")))
    name = slug(str(service.get("name", "")))
    if not service_id:
        return 0
    if wanted == service_id:
        return 100
    if service_id == f"{wanted}data":
        return 90
    if wanted in service_id:
        return 70 if "sme" not in service_id else 20
    if name.startswith(wanted):
        return 60
    if wanted in name:
        return 50
    return 0


def _load_fixtures(fixtures: Path, name: str) -> dict:
    if not name:
        return {}
    path = fixtures / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


# One shared catalog: fixtures are read once per process.
CATALOG = Catalog()
