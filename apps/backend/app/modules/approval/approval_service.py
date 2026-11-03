"""Payments over a limit wait for the owner instead of just being refused.

When the agent is asked for a payment that breaks the per-payment or monthly cap,
it files a request here and tells the person it is waiting. Only the owner, signed
in to the app, can approve it — never a chat, so a voice in the room can ask but
can never also say yes. An approved request pays that one amount, once, past the
caps it broke; the balance, the pause and the vendor still apply. A request lapses
after the account's approval window and then pays nothing.

The other refusals (a paused Stark, an unlisted meter, a short balance) are not
the owner's to wave through from here, so they never become requests.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.common.api_error import ApiError
from app.common.clock import Clock
from app.modules.approval.approval_repository import ApprovalRepository
from app.modules.payment.bill_payment_service import BillPaymentService

PENDING = "pending"
APPROVED = "approved"
DENIED = "denied"
EXPIRED = "expired"

WINDOWS_MINUTES = (15, 30, 60, 360, 1440)
DEFAULT_WINDOW_MINUTES = 60


class ApprovalService:
    def __init__(self, repository: ApprovalRepository,
                 bill_payments: BillPaymentService) -> None:
        self.repository = repository
        self.bill_payments = bill_payments

    def window_minutes(self, account_id: str) -> int:
        return self.repository.window(account_id) or DEFAULT_WINDOW_MINUTES

    def set_window(self, account_id: str, minutes: int) -> None:
        if minutes not in WINDOWS_MINUTES:
            raise ApiError(400, "bad_limits",
                           f"approval_window_minutes must be one of {list(WINDOWS_MINUTES)}")
        self.repository.set_window(account_id, minutes)

    def request(self, account_id: str, bill: dict[str, Any], amount_ngn: int,
                reason: str) -> dict[str, Any]:
        """File one request, or hand back the live one for this exact payment."""
        now = Clock.now_iso()
        existing = self.repository.open_for(account_id, bill["id"], amount_ngn, now)
        if existing is not None:
            return existing
        return self.repository.create(account_id, {
            "id": f"req_{uuid.uuid4().hex[:10]}",
            "bill_id": bill["id"],
            "bill_label": bill["label"],
            "amount_ngn": amount_ngn,
            "reason": reason,
            "status": PENDING,
            "created_at": now,
            "expires_at": Clock.in_minutes(self.window_minutes(account_id)),
        })

    def recent(self, account_id: str) -> list[dict[str, Any]]:
        self.repository.expire_lapsed(account_id, Clock.now_iso())
        return self.repository.recent(account_id)

    def approve(self, account_id: str, request_id: str) -> dict[str, Any]:
        """Pay this one request past the caps it broke. Returns the request and receipt."""
        request = self._claim(account_id, request_id, APPROVED)
        try:
            receipt = self.bill_payments.pay(account_id, request["bill_id"],
                                             request["amount_ngn"], approved=True)
        except ApiError:
            # Nothing was charged (short balance, paused, vendor failed): leave it
            # waiting, so the owner can fix the cause and approve again in time.
            self.repository.reopen(account_id, request_id)
            raise
        self.repository.attach_receipt(account_id, request_id, receipt["id"])
        request["receipt_id"] = receipt["id"]
        return {"request": request, "receipt": receipt}

    def deny(self, account_id: str, request_id: str) -> dict[str, Any]:
        request = self._claim(account_id, request_id, DENIED)
        self.bill_payments.record_declined(
            account_id, request["bill_id"], request["bill_label"], request["amount_ngn"],
            "You declined this payment.",
        )
        return request

    def _claim(self, account_id: str, request_id: str, status: str) -> dict[str, Any]:
        claimed = self.repository.claim(account_id, request_id, status, Clock.now_iso())
        if claimed is not None:
            return claimed
        existing = self.repository.get(account_id, request_id)
        if existing is None:
            raise ApiError(404, "unknown_request", "No payment request with that id.",
                           {"request_id": request_id})
        self.repository.expire_lapsed(account_id, Clock.now_iso())
        current = self.repository.get(account_id, request_id)
        raise ApiError(409, "request_closed",
                       "That request has already been decided or has expired.",
                       {"request_id": request_id, "status": current["status"]})
