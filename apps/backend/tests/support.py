"""A throwaway account on the real database, for tests that store something.

The stores take an account id now, because accounts are real: every row belongs to
somebody. Tests do not care about that, they care about the receipt they just wrote,
so this binds the id once and lets the test call the store the way it always did.

Each account is created fresh (`test_<random>`) and deleted with `close()`, which
cascades through receipts, wallet and identities. So tests share a database without
sharing data — and without a second schema, a fixture file, or a local Postgres
container pretending to be the one the app actually uses.

The cost is honest and worth stating: these tests need `DATABASE_URL` and a network,
and each store call is a ~250 ms round trip.
"""

from __future__ import annotations

import secrets
from dataclasses import replace
from typing import Any

from fastapi.testclient import TestClient

from app.app_module import AppModule
from app.database import neon
from app.decorators.auth_user import auth_guard
from app.main import create_app
from app.modules.account.account import Account
from app.modules.payment import payment_service
from app.modules.receipt import receipt_repository
from app.shared.services.api_config_service import ApiConfigService

# The store methods that are scoped to an account. Everything else (`close`) is not.
_ACCOUNT_SCOPED = frozenset({
    "create", "update", "get", "by_request_id", "has_pending", "find_pending",
    "recent", "count", "wallet", "set_wallet", "record_deposit",
    "record_withdrawal", "added_this_month", "charge", "replace_all",
})


class BoundStore:
    """A `ReceiptRepository` with the account id filled in.

    Exists so a test can say `store.wallet()` rather than `store.wallet(ACCOUNT)`
    on every line, while the store itself stays unaware of who is calling.
    """

    def __init__(self, store: receipt_repository.ReceiptRepository, user_id: str) -> None:
        self.raw = store
        self.user_id = user_id

    def __getattr__(self, name: str):
        attribute = getattr(self.raw, name)
        if name not in _ACCOUNT_SCOPED:
            return attribute

        def scoped(*args: Any, **kwargs: Any):
            return attribute(self.user_id, *args, **kwargs)

        return scoped


class BoundPayments:
    """A `PaymentService` with the account id filled in."""

    def __init__(self, service: payment_service.PaymentService, user_id: str) -> None:
        self.raw = service
        self.user_id = user_id

    def pay(self, bill: dict, amount_ngn: int, **kwargs: Any) -> dict:
        return self.raw.pay(self.user_id, bill, amount_ngn, **kwargs)

    def recent(self, limit: int = 20) -> list[dict]:
        return self.raw.recent(self.user_id, limit)

    def wallet(self) -> dict[str, int]:
        return self.raw.wallet(self.user_id)


class TempAccount:
    """A real account row, a bound store, and a cleanup that leaves no trace."""

    def __init__(self, *, balance_ngn: int = 0, spent_ngn: int = 0,
                 db: neon.Database | None = None) -> None:
        self.db = db or neon.open_database()
        self.id = f"test_{secrets.token_hex(8)}"
        self.db.query(
            "INSERT INTO accounts (id, auth_user_id, email, name, created_at)"
            " VALUES ($1, $2, $3, $4, $5)",
            [self.id, f"auth-{self.id}", f"{self.id}@test.invalid", "Test Account",
             "2026-10-26T00:00:00Z"],
        )
        self.store = BoundStore(receipt_repository.ReceiptRepository(self.db), self.id)
        if balance_ngn or spent_ngn:
            self.store.set_wallet(balance_ngn, spent_ngn)

    def payments(self, gateway) -> BoundPayments:
        return BoundPayments(
            payment_service.PaymentService(self.store.raw, gateway), self.id
        )

    def close(self) -> None:
        self.db.query("DELETE FROM accounts WHERE id = $1", [self.id])


class ApiHarness:
    """The real app on the real database, signed in as a `TempAccount`.

    Routes run exactly as a client sees them (DTOs, error filter, status codes);
    only the auth guard is swapped, so no Neon Auth session is needed. `opened`
    says whether the account counts as already opened, which is what the session
    lookup normally reports: a new account is opened (₦0 wallet) on first sight.
    """

    def __init__(self, account: TempAccount, *, opened: bool = True,
                 **config: Any) -> None:
        settings = replace(ApiConfigService.from_env(), reminders_enabled=False, **config)
        self.account = account
        self.opened = opened
        self.module = AppModule(settings, account.db)
        app = create_app(self.module)
        app.dependency_overrides[auth_guard] = self._sign_in
        self.client = TestClient(app)

    def _sign_in(self) -> Account:
        self.module.accounts.state(self.account.id, opened=self.opened)
        return Account(id=self.account.id, email=f"{self.account.id}@test.invalid",
                       name="Test Account")

    def state(self):
        """This account's in-process state (bills, caps, agent)."""
        return self.module.accounts.state(self.account.id, opened=self.opened)

    def restart(self) -> None:
        """Forget the in-process copy, as a fresh server process would."""
        self.module.accounts.forget(self.account.id)
