"""`GET /v1/state`: everything the dashboard (and the agent) needs in one read."""

from __future__ import annotations

from typing import Any

from app.common.clock import Clock
from app.modules.account.account_service import AccountService
from app.modules.reminder import reminders
from app.modules.telemetry.telemetry_service import TelemetryService
from app.modules.wallet.wallet_service import WalletService


class StateService:
    def __init__(self, accounts: AccountService, wallet: WalletService,
                 telemetry: TelemetryService) -> None:
        self.accounts = accounts
        self.wallet = wallet
        self.telemetry = telemetry

    def snapshot(self, account_id: str) -> dict[str, Any]:
        state = self.accounts.state(account_id)
        wallet = self.wallet.balance(account_id)
        cap = state.limits.monthly_cap_ngn
        units_left, days_left = self.telemetry.meter_reading(account_id, state.bills)
        return {
            "user_id": account_id,
            "first_name": state.first_name,
            "currency": "NGN",
            "balance_ngn": wallet["balance_ngn"],
            "cap_ngn": cap,
            "spent_ngn": wallet["spent_ngn"],
            "remaining_cap_ngn": max(cap - wallet["spent_ngn"], 0),
            "units_left": units_left,
            "days_left": days_left,
            "bills": list(state.bills.values()),
            # Bills with a renewal inside the reminder window, soonest first. The
            # agent's snapshot and the dashboard's "Stark noticed" block read it here.
            "due_soon": reminders.due_soon(state.bills.values()),
            "as_of": Clock.now_iso(),
        }
