"""What Stark notices on its own — computed from live state, never invented.

Every line comes from `suggestions.build`: the meter, the wallet, delivered
receipts, readings and the renewal calendar. A signal without data behind it is not
returned, and an empty list is the honest answer when nothing needs attention.
"""

from __future__ import annotations

from typing import Any

from app.modules.account.account_service import AccountService
from app.modules.payment.bill_payment_service import BillPaymentService
from app.modules.suggestion import suggestions
from app.modules.telemetry.telemetry_service import TelemetryService
from app.modules.wallet.wallet_service import WalletService


class SuggestionService:
    TARIFF_NGN_PER_KWH = 209.0

    def __init__(self, accounts: AccountService, wallet: WalletService,
                 telemetry: TelemetryService, payments: BillPaymentService) -> None:
        self.accounts = accounts
        self.wallet = wallet
        self.telemetry = telemetry
        self.payments = payments

    def suggestions(self, account_id: str) -> list[dict[str, Any]]:
        state = self.accounts.state(account_id)
        units_left, days_left = self.telemetry.meter_reading(account_id, state.bills)
        return suggestions.build(
            bills=list(state.bills.values()),
            units_left=units_left,
            days_left=days_left,
            spent_ngn=self.wallet.balance(account_id)["spent_ngn"],
            cap_ngn=state.limits.monthly_cap_ngn,
            telemetry=self.telemetry.recent_load(account_id),
            receipts=self.payments.recent(account_id, 50),
            tariff_ngn_per_kwh=self.TARIFF_NGN_PER_KWH,
        )
