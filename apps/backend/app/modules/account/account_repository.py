"""What an account owns besides money: its saved bills and its spending limits.

Both lived in process memory until 2026-10-27, so a restart quietly brought back
the artboard's three bills and the default caps. They live in Postgres now, next to
the wallet and receipts, and every handler that changes one writes it through here.
"""

from __future__ import annotations

import json
from typing import Any

from app.database import neon


class AccountRepository:
    def __init__(self, db: neon.Database | None = None) -> None:
        self.db = db or neon.open_database()

    def bills(self, user_id: str) -> dict[str, dict[str, Any]]:
        rows = self.db.query(
            "SELECT data FROM bills WHERE user_id = $1 ORDER BY seq", [user_id]
        )
        loaded = [json.loads(row["data"]) for row in rows]
        return {bill["id"]: bill for bill in loaded}

    def save_bill(self, user_id: str, bill: dict[str, Any]) -> None:
        self.db.query(
            "INSERT INTO bills (user_id, id, data) VALUES ($1, $2, $3)"
            " ON CONFLICT (user_id, id) DO UPDATE SET data = EXCLUDED.data",
            [user_id, bill["id"], json.dumps(bill)],
        )

    def delete_bill(self, user_id: str, bill_id: str) -> None:
        self.db.query(
            "DELETE FROM bills WHERE user_id = $1 AND id = $2", [user_id, bill_id]
        )

    def replace_bills(self, user_id: str, bills: list[dict[str, Any]]) -> None:
        self.db.query("DELETE FROM bills WHERE user_id = $1", [user_id])
        for bill in bills:
            self.save_bill(user_id, bill)

    def limits(self, user_id: str) -> tuple[int, int] | None:
        row = self.db.one(
            "SELECT monthly_cap_ngn, per_payment_cap_ngn FROM account_limits"
            " WHERE user_id = $1",
            [user_id],
        )
        if row is None:
            return None
        return int(row["monthly_cap_ngn"]), int(row["per_payment_cap_ngn"])

    def set_limits(self, user_id: str, monthly_cap_ngn: int,
                   per_payment_cap_ngn: int) -> None:
        self.db.query(
            "INSERT INTO account_limits (user_id, monthly_cap_ngn, per_payment_cap_ngn)"
            " VALUES ($1, $2, $3)"
            " ON CONFLICT (user_id) DO UPDATE SET"
            "   monthly_cap_ngn = EXCLUDED.monthly_cap_ngn,"
            "   per_payment_cap_ngn = EXCLUDED.per_payment_cap_ngn",
            [user_id, monthly_cap_ngn, per_payment_cap_ngn],
        )
