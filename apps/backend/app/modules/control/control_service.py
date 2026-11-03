"""The owner's off switch: pause Stark, and resume it.

A pause is stored on the account and checked by every payment path — the agent's
gate (`policy.check_payment`) and `POST /v1/payments` — so a paused account cannot
be charged by voice, chat, the app or a reminder. Reading and paying stay separate:
a paused Stark still answers questions, it just pays nothing.
"""

from __future__ import annotations

from typing import Any

from app.common.clock import Clock
from app.modules.account.account_repository import AccountRepository
from app.modules.account.account_service import AccountService
from app.modules.vault.vault_service import VaultService


class ControlService:
    def __init__(self, accounts: AccountService, repository: AccountRepository,
                 vaults: VaultService) -> None:
        self.accounts = accounts
        self.repository = repository
        self.vaults = vaults

    def status(self, account_id: str) -> dict[str, Any]:
        paused_at = self.accounts.state(account_id).paused_at
        return {"paused": paused_at is not None, "paused_at": paused_at}

    def pause(self, account_id: str) -> dict[str, Any]:
        """Idempotent: pausing a paused account keeps the original time."""
        state = self.accounts.state(account_id)
        if state.paused_at is None:
            state.paused_at = Clock.now_iso()
            self.repository.set_paused_at(account_id, state.paused_at)
            self.vaults.set_paused(account_id, True)
        return self.status(account_id)

    def resume(self, account_id: str) -> dict[str, Any]:
        state = self.accounts.state(account_id)
        if state.paused_at is not None:
            state.paused_at = None
            self.repository.set_paused_at(account_id, None)
            self.vaults.set_paused(account_id, False)
        return self.status(account_id)
