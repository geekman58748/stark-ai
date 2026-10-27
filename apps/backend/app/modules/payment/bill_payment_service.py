"""Paying a saved bill: the contract's checks, then the purchase.

Shared by `POST /v1/payments` and the agent, so both refuse with the same codes in
the same order: the per-payment cap first, then the monthly cap, then the balance.
The purchase itself, and the charge that only follows a delivery, happen in
`PaymentService`, which records the intent before it calls the vendor.
"""

from __future__ import annotations

from typing import Any, Optional

from app.common.api_error import ApiError
from app.modules.account.account_service import AccountService
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
            tx_hash: Optional[str] = None) -> dict[str, Any]:
        bill = self.bills.get(account_id, bill_id)
        if amount <= 0:
            raise ApiError(400, "bad_amount", "amount_ngn must be positive")

        limits = self.accounts.state(account_id).limits
        wallet = self.wallet.balance(account_id)
        spent, balance = wallet["spent_ngn"], wallet["balance_ngn"]
        if amount > limits.per_payment_cap_ngn:
            raise ApiError(409, "over_per_payment_cap",
                           "That's over the most you allow in one go.",
                           {"amount_ngn": amount, "cap_ngn": limits.per_payment_cap_ngn})
        if spent + amount > limits.monthly_cap_ngn:
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

    def recent(self, account_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self.payments.recent(account_id, limit)
