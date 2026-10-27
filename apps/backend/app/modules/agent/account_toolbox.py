"""The agent's view of one account. Deliberately thin: it may read state and pay a
bill, and nothing else."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.common.api_error import ApiError
from app.modules.agent import agent as agent_layer

if TYPE_CHECKING:
    from app.app_module import AppModule


class AccountToolbox:
    def __init__(self, account_id: str, module: "AppModule") -> None:
        self.account_id = account_id
        self.module = module

    def get_state(self) -> dict:
        return self.module.state.snapshot(self.account_id)

    def list_bills(self) -> list[dict]:
        return list(self.module.bills.bills(self.account_id).values())

    def recent_activity(self) -> list[dict]:
        return self.module.bill_payments.recent(self.account_id, 20)

    def pay(self, bill_id: str, amount_ngn: int) -> dict:
        try:
            return self.module.bill_payments.pay(self.account_id, bill_id, amount_ngn)
        except ApiError as err:
            raise agent_layer.PaymentError(err.code, err.message, err.detail) from err
