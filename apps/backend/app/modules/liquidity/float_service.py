"""The VTpass float: the naira Stark fronts so a deposit can be spent at once.

Every purchase is paid out of one merchant wallet at VTpass, not out of the user's
money. So before a payment is signed, this checks that the float can cover it:

    available = VTpass balance − purchases still pending

A pending purchase has been sent to VTpass and may still be charged, so it is
counted as spent. If the payment does not fit, it is refused with `float_low`
(nothing signed, nothing charged) and a refill is started.

**Refilling** is a Bachs payout from Stark's naira balance to the bank account
VTpass funds the wallet from (`VTPASS_FUNDING_DESTINATION`, a Bachs `pd_` id that
has passed Bachs's review). VTpass credits the wallet when the transfer lands.
Without Bachs or a destination, the refill is recorded as `manual` and logged — the
operator tops VTpass up by hand — which is honest about what happened.

One refill is open at a time; `payout.paid` / `payout.failed` close it.

| Variable | Default | Meaning |
|---|---|---|
| `STARK_FLOAT_LOW_NGN` | 100,000 | refill when the balance falls under this |
| `STARK_FLOAT_TARGET_NGN` | 500,000 | refill up to this |
| `VTPASS_FUNDING_DESTINATION` | — | Bachs payout destination for VTpass funding |
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from app.common.api_error import ApiError
from app.common.clock import Clock
from app.database import neon
from app.modules.bachs.bachs import BachsClient, BachsError
from app.modules.vending.vtpass import VtpassClient, VtpassError

log = logging.getLogger("stark.float")

FLOAT_LOW_MESSAGE = (
    "I can't buy that right now, so nothing was charged. Try again in a few minutes."
)


@dataclass(frozen=True)
class FloatSettings:
    low_water_ngn: int
    target_ngn: int
    funding_destination: Optional[str]
    cache_seconds: int = 60


class FloatService:
    def __init__(self, db: neon.Database, vtpass: VtpassClient, bachs: Optional[BachsClient],
                 settings: FloatSettings) -> None:
        self.db = db
        self.vtpass = vtpass
        self.bachs = bachs
        self.settings = settings
        self._cached: Optional[tuple[float, int]] = None
        self._lock = threading.Lock()

    # --- reading --------------------------------------------------------------

    def balance(self, *, fresh: bool = False) -> int:
        with self._lock:
            if not fresh and self._cached is not None \
                    and time.monotonic() - self._cached[0] < self.settings.cache_seconds:
                return self._cached[1]
        value = self.vtpass.balance()
        with self._lock:
            self._cached = (time.monotonic(), value)
        return value

    def reserved(self) -> int:
        return int(self.db.value(
            "SELECT COALESCE(SUM(amount_ngn), 0) FROM receipts WHERE status = 'pending'"
        ) or 0)

    def available(self) -> int:
        return self.balance() - self.reserved()

    # --- the check ------------------------------------------------------------

    def ensure_can_cover(self, amount_ngn: int) -> None:
        """Refuse before anything is signed when the float cannot cover the purchase.

        A float that cannot be read is treated the same way: buying blind is how
        a user ends up with a `018` halfway through a purchase.
        """
        try:
            available = self.available()
        except VtpassError as err:
            log.warning("float unreadable: %s", err)
            raise ApiError(503, "float_low", FLOAT_LOW_MESSAGE) from err
        if amount_ngn > available:
            self.request_refill()
            raise ApiError(503, "float_low", FLOAT_LOW_MESSAGE,
                           {"amount_ngn": amount_ngn})

    def check_level(self) -> None:
        """Read the float fresh and refill it if it is low. Runs after every delivered
        purchase and on every money-loop tick."""
        try:
            balance = self.balance(fresh=True)
        except VtpassError:
            return
        if balance < self.settings.low_water_ngn:
            self.request_refill()

    # --- refilling ------------------------------------------------------------

    def request_refill(self) -> Optional[dict[str, Any]]:
        """Start one refill, unless one is already open. Returns the open refill."""
        open_refill = self.db.one(
            "SELECT * FROM float_refills WHERE status IN ('requested', 'sent', 'manual')"
            " ORDER BY created_at DESC LIMIT 1"
        )
        if open_refill is not None:
            return open_refill
        try:
            balance = self.balance(fresh=True)
        except VtpassError:
            balance = 0
        # Round up to the next ₦10,000 so refills are few and easy to reconcile.
        shortfall = max(self.settings.target_ngn - balance, 0)
        amount = -(-shortfall // 10_000) * 10_000
        if amount == 0:
            return None

        refill_id = f"refill_{uuid.uuid4().hex[:12]}"
        now = Clock.now_iso()
        automatic = self.bachs is not None and self.settings.funding_destination
        status = "requested" if automatic else "manual"
        row = self.db.one(
            "INSERT INTO float_refills (id, amount_ngn, status, created_at, updated_at)"
            " VALUES ($1, $2, $3, $4, $4)"
            " ON CONFLICT DO NOTHING RETURNING *",
            [refill_id, amount, status, now],
        )
        if not automatic:
            log.warning("VTpass float is ₦%s; top it up by ₦%s by hand (%s)",
                        f"{balance:,}", f"{amount:,}", refill_id)
            return row
        return self._send_refill(refill_id, amount)

    def _send_refill(self, refill_id: str, amount_ngn: int) -> Optional[dict[str, Any]]:
        assert self.bachs is not None and self.settings.funding_destination
        try:
            payout = self.bachs.create_payout(
                destination=self.settings.funding_destination, amount_ngn=amount_ngn,
                reference=refill_id, narration="Stark float",
            )
        except BachsError as err:
            return self._close(refill_id, "failed", None, err.message)
        return self._close(refill_id, "sent", payout["id"], None)

    def on_payout(self, reference: str, paid: bool) -> bool:
        """Close the refill a payout webhook is about. False if it isn't a refill."""
        if not reference.startswith("refill_"):
            return False
        self._close(reference, "paid" if paid else "failed", None, None)
        with self._lock:
            self._cached = None
        return True

    def _close(self, refill_id: str, status: str, payout_id: Optional[str],
               error: Optional[str]) -> Optional[dict[str, Any]]:
        return self.db.one(
            "UPDATE float_refills SET status = $2, payout_id = COALESCE($3, payout_id),"
            " last_error = $4, updated_at = $5 WHERE id = $1 RETURNING *",
            [refill_id, status, payout_id, error, Clock.now_iso()],
        )

    def mark_manual_refill_done(self, refill_id: str) -> Optional[dict[str, Any]]:
        """The operator topped VTpass up by hand."""
        with self._lock:
            self._cached = None
        return self._close(refill_id, "paid", None, None)
