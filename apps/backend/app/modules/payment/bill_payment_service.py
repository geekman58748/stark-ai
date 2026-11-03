"""Paying a saved bill: the contract's checks, then the purchase.

Shared by `POST /v1/payments` and the agent, so both refuse with the same codes in
the same order: the per-payment cap first, then the monthly cap, then the balance.
The purchase itself, and the charge that only follows a delivery, happen in
`PaymentService`, which records the intent before it calls the vendor.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from app.common.api_error import ApiError
from app.common.clock import Clock
from app.modules.account.account_service import AccountService
from app.modules.agent import policy
from app.modules.bill.bill_service import BillService
from app.modules.payment import payment_service
from app.modules.payment.payment_service import PaymentService
from app.modules.receipt import receipt_repository
from app.modules.wallet.wallet_service import WalletService


class BillPaymentService:
    def __init__(self, accounts: AccountService, bills: BillService,
                 wallet: WalletService, payments: PaymentService) -> None:
        self.accounts = accounts
        self.bills = bills
        self.wallet = wallet
        self.payments = payments

    def pay(self, account_id: str, bill_id: str, amount: int,
            tx_hash: Optional[str] = None, *, approved: bool = False) -> dict[str, Any]:
        """`approved` is the owner lifting the caps for this one payment (see
        `ApprovalService`); the pause and the balance still apply."""
        bill = self.bills.get(account_id, bill_id)
        state = self.accounts.state(account_id)
        if state.paused_at is not None:
            raise ApiError(423, policy.PAUSED, policy.MESSAGES[policy.PAUSED])
        if amount <= 0:
            raise ApiError(400, "bad_amount", "amount_ngn must be positive")

        limits = state.limits
        wallet = self.wallet.balance(account_id)
        spent, balance = wallet["spent_ngn"], wallet["balance_ngn"]
        if not approved and amount > limits.per_payment_cap_ngn:
            raise ApiError(409, "over_per_payment_cap",
                           "That's over the most you allow in one go.",
                           {"amount_ngn": amount, "cap_ngn": limits.per_payment_cap_ngn})
        if not approved and spent + amount > limits.monthly_cap_ngn:
            raise ApiError(409, "over_cap", "That would go over your monthly limit.", {
                "cap_ngn": limits.monthly_cap_ngn,
                "spent_ngn": spent,
                "remaining_ngn": max(limits.monthly_cap_ngn - spent, 0),
            })
        if amount > balance:
            raise ApiError(409, "insufficient_balance",
                           "Not enough in your wallet. Add money first.",
                           {"balance_ngn": balance, "amount_ngn": amount})

        try:
            receipt = self.payments.pay(account_id, bill, amount, tx_hash=tx_hash)
        except payment_service.SpendError as err:
            status = 409 if err.code == payment_service.INSUFFICIENT_BALANCE else 502
            raise ApiError(status, err.code, err.message, err.detail) from err

        if receipt.get("status") == "delivered":
            self.bills.apply_delivery(account_id, receipt)
        return receipt_repository.api_shape(receipt)

    def record_declined(self, account_id: str, bill_id: str, bill_label: str,
                        amount: int, reason: str) -> dict[str, Any]:
        """An activity row for a payment Stark refused or the owner denied.

        It never touches the wallet: `declined` is not a charge and not a spend.
        """
        return receipt_repository.api_shape(self.payments.store.create(account_id, {
            "id": f"rcpt_{uuid.uuid4().hex[:6]}",
            "request_id": f"dec_{uuid.uuid4().hex[:12]}",
            "bill_id": bill_id,
            "bill_label": bill_label,
            "meter": None,
            "amount_ngn": amount,
            "units": None,
            "token": None,
            "tx_hash": None,
            "status": "declined",
            "entry_type": "bill",
            "source": "Stark",
            "vendor": None,
            "vendor_code": None,
            "vendor_message": reason,
            "created_at": Clock.now_iso(),
        }))

    def recent(self, account_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self.payments.recent(account_id, limit)
