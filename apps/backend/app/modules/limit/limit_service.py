"""The owner's spending caps. A change takes effect for the agent immediately."""

from __future__ import annotations

from typing import Any

from app.common.api_error import ApiError
from app.modules.account.account_service import AccountService
from app.modules.limit.dtos.update_limits_dto import UpdateLimitsDto
from app.modules.wallet.wallet_service import WalletService


class LimitService:
    def __init__(self, accounts: AccountService, wallet: WalletService) -> None:
        self.accounts = accounts
        self.wallet = wallet

    def summary(self, account_id: str) -> dict[str, Any]:
        limits = self.accounts.state(account_id).limits
        spent = self.wallet.balance(account_id)["spent_ngn"]
        return {
            "monthly_cap_ngn": limits.monthly_cap_ngn,
            "per_payment_cap_ngn": limits.per_payment_cap_ngn,
            "spent_ngn": spent,
            "remaining_cap_ngn": max(limits.monthly_cap_ngn - spent, 0),
        }

    def update(self, account_id: str, dto: UpdateLimitsDto) -> dict[str, Any]:
        monthly, per = dto.monthly_cap_ngn, dto.per_payment_cap_ngn
        if monthly is not None and monthly <= 0:
            raise ApiError(400, "bad_limits", "monthly_cap_ngn must be positive")
        if per is not None and per <= 0:
            raise ApiError(400, "bad_limits", "per_payment_cap_ngn must be positive")
        current = self.accounts.state(account_id).limits
        effective_monthly = current.monthly_cap_ngn if monthly is None else monthly
        effective_per = current.per_payment_cap_ngn if per is None else per
        if effective_per > effective_monthly:
            raise ApiError(400, "bad_limits",
                           "The per-payment limit can't exceed the monthly limit.")
        self.accounts.rebuild_limits(account_id, monthly_cap_ngn=monthly,
                                     per_payment_cap_ngn=per)
        return self.summary(account_id)
