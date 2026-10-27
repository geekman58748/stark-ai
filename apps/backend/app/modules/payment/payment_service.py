"""A payment, in the order it actually happens.

    policy check (agent)  →  sign pay()  →  THIS  →  receipt

Inside "this", the transaction has two phases:

1. **Record it before buying.** The receipt exists with a `request_id` and status
   `pending` *before* the vendor is called. If the process dies mid-purchase, the id
   survives and the purchase can be re-queried instead of duplicated — which is the
   only way to survive VTpass's duplicate rule (`019`).
2. **Charge only on delivery.** `pending` and `failed` never move money. A retry of
   the same intent re-queries the same `request_id` and settles it if the vendor
   delivered in the meantime.

Charging moves the balance and writes the receipt in one statement, so the balance
and the history cannot disagree after a restart.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Callable

from app.modules.receipt import receipt_repository as receipts_mod
from app.modules.vending import vtpass
from app.modules.vending import vending as vending_mod
from app.modules.receipt.receipt_repository import ReceiptRepository
from app.modules.vending.vending import VendingGateway, VendingOutcome

# Errors the HTTP layer turns into a response.
VENDOR_FAILED = "vendor_failed"
INSUFFICIENT_BALANCE = "insufficient_balance"


class SpendError(Exception):
    def __init__(self, code: str, message: str, detail: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class PaymentService:
    def __init__(
        self,
        store: ReceiptRepository,
        gateway: VendingGateway,
        *,
        clock: Callable[[], str] = _now_iso,
    ):
        self.store = store
        self.gateway = gateway
        self.clock = clock

    def pay(self, user_id: str, bill: dict, amount_ngn: int, *,
            tx_hash: str | None = None) -> dict:
        """Book a payment for one account. Returns the stored receipt row."""
        pending = self.store.find_pending(user_id, bill["id"], amount_ngn)
        if pending is not None:
            return self._settle_retry(user_id, pending, amount_ngn)

        receipt = self.store.create(
            user_id,
            {
                "id": f"rcpt_{uuid.uuid4().hex[:6]}",
                "request_id": vtpass.new_request_id(),
                "bill_id": bill["id"],
                "bill_label": bill["label"],
                "meter": str(bill.get("reference") or ""),
                "amount_ngn": amount_ngn,
                "units": None,
                "token": None,
                "tx_hash": tx_hash,
                "status": vending_mod.PENDING,
                "vendor": None,
                "vendor_code": None,
                "vendor_message": None,
                "created_at": self.clock(),
            }
        )

        outcome = self.gateway.buy(bill, amount_ngn, receipt["request_id"])
        return self._apply(user_id, receipt, outcome, amount_ngn)

    def _settle_retry(self, user_id: str, pending: dict, amount_ngn: int) -> dict:
        outcome = self.gateway.requery(pending["request_id"], amount_ngn)
        if outcome.status == vending_mod.FAILED:
            self.store.update(
                user_id,
                pending["id"],
                status=vending_mod.FAILED,
                vendor_code=outcome.code,
                vendor_message=outcome.message,
            )
            raise SpendError(VENDOR_FAILED, outcome.message, {"code": outcome.code})
        return self._apply(user_id, pending, outcome, amount_ngn)

    def _apply(
        self, user_id: str, receipt: dict, outcome: VendingOutcome, amount_ngn: int
    ) -> dict:
        common = {
            "vendor": outcome.vendor,
            "vendor_code": outcome.code,
            "vendor_message": outcome.message,
        }

        if outcome.status == vending_mod.FAILED:
            self.store.update(user_id, receipt["id"], status=vending_mod.FAILED, **common)
            raise SpendError(VENDOR_FAILED, outcome.message, {"code": outcome.code})

        if (
            outcome.status == vending_mod.DELIVERED
            and outcome.token_required
            and not outcome.token
        ):
            # A metered product that reports delivered with no token is not something
            # to charge for. Treat it as still in flight and let the retry settle it.
            # Airtime and TV legitimately have no token, so they skip this.
            self.store.update(user_id, receipt["id"], status=vending_mod.PENDING, **common)
            return self.store.get(user_id, receipt["id"])  # type: ignore[return-value]

        if not outcome.ok:
            self.store.update(user_id, receipt["id"], status=vending_mod.PENDING, **common)
            return self.store.get(user_id, receipt["id"])  # type: ignore[return-value]

        try:
            self.store.charge(user_id, amount_ngn)
        except ValueError:
            failure = dict(common)
            failure["vendor_message"] = "insufficient balance at settlement"
            self.store.update(user_id, receipt["id"], status=vending_mod.FAILED, **failure)
            raise SpendError(
                INSUFFICIENT_BALANCE,
                "There isn't enough in your balance for that.",
                {"amount_ngn": amount_ngn},
            ) from None

        return self.store.update(
            user_id,
            receipt["id"],
            status=outcome.status,
            token=outcome.token,
            units=outcome.units,
            **common,
        )  # type: ignore[return-value]

    # --- read side -----------------------------------------------------------

    def recent(self, user_id: str, limit: int = 20) -> list[dict]:
        return [receipts_mod.api_shape(row) for row in self.store.recent(user_id, limit)]

    def wallet(self, user_id: str) -> dict[str, int]:
        return self.store.wallet(user_id) or {"balance_ngn": 0, "spent_ngn": 0}
