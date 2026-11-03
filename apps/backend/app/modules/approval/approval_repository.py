"""Payment requests waiting on the owner, one row each, scoped per account.

A decision is a single conditional `UPDATE ... WHERE status = 'pending' AND
expires_at > now`, so two taps on Approve (or Approve racing the expiry) can only
ever claim the request once. Times are the `Clock` ISO shape, which sorts as text.
"""

from __future__ import annotations

from typing import Any

from app.database import neon

COLUMNS = (
    "id", "user_id", "bill_id", "bill_label", "amount_ngn", "reason", "status",
    "created_at", "expires_at", "decided_at", "receipt_id",
)


def _typed(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """Neon returns BIGINT as a string; money is an int the moment it leaves a query."""
    if row is not None:
        row["amount_ngn"] = int(row["amount_ngn"])
    return row


class ApprovalRepository:
    def __init__(self, db: neon.Database) -> None:
        self.db = db

    def create(self, user_id: str, request: dict[str, Any]) -> dict[str, Any]:
        columns = ", ".join(COLUMNS)
        placeholders = ", ".join(f"${i}" for i in range(1, len(COLUMNS) + 1))
        values = [user_id if c == "user_id" else request.get(c) for c in COLUMNS]
        return _typed(self.db.one(
            f"INSERT INTO payment_requests ({columns}) VALUES ({placeholders}) RETURNING *",
            values,
        ))

    def get(self, user_id: str, request_id: str) -> dict[str, Any] | None:
        return _typed(self.db.one(
            "SELECT * FROM payment_requests WHERE user_id = $1 AND id = $2",
            [user_id, request_id],
        ))

    def open_for(self, user_id: str, bill_id: str, amount_ngn: int,
                 now: str) -> dict[str, Any] | None:
        """The live request for this exact payment, so asking twice waits once."""
        return _typed(self.db.one(
            "SELECT * FROM payment_requests WHERE user_id = $1 AND bill_id = $2"
            " AND amount_ngn = $3 AND status = 'pending' AND expires_at > $4"
            " ORDER BY seq DESC LIMIT 1",
            [user_id, bill_id, amount_ngn, now],
        ))

    def recent(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return [_typed(row) for row in self.db.query(
            "SELECT * FROM payment_requests WHERE user_id = $1 ORDER BY seq DESC LIMIT $2",
            [user_id, limit],
        )]

    def expire_lapsed(self, user_id: str, now: str) -> None:
        self.db.query(
            "UPDATE payment_requests SET status = 'expired', decided_at = expires_at"
            " WHERE user_id = $1 AND status = 'pending' AND expires_at <= $2",
            [user_id, now],
        )

    def claim(self, user_id: str, request_id: str, status: str,
              now: str) -> dict[str, Any] | None:
        """Move a live request to `status`, or None if it was already decided or lapsed."""
        return _typed(self.db.one(
            "UPDATE payment_requests SET status = $3, decided_at = $4"
            " WHERE user_id = $1 AND id = $2 AND status = 'pending' AND expires_at > $4"
            " RETURNING *",
            [user_id, request_id, status, now],
        ))

    def reopen(self, user_id: str, request_id: str) -> None:
        """Undo a claim whose payment did not go through, so it can be approved again."""
        self.db.query(
            "UPDATE payment_requests SET status = 'pending', decided_at = NULL"
            " WHERE user_id = $1 AND id = $2",
            [user_id, request_id],
        )

    def attach_receipt(self, user_id: str, request_id: str, receipt_id: str) -> None:
        self.db.query(
            "UPDATE payment_requests SET receipt_id = $3 WHERE user_id = $1 AND id = $2",
            [user_id, request_id, receipt_id],
        )

    def window(self, user_id: str) -> int | None:
        row = self.db.one("SELECT approval_window_minutes FROM accounts WHERE id = $1",
                          [user_id])
        return None if row is None or row["approval_window_minutes"] is None else int(
            row["approval_window_minutes"])

    def set_window(self, user_id: str, minutes: int) -> None:
        self.db.query("UPDATE accounts SET approval_window_minutes = $1 WHERE id = $2",
                      [minutes, user_id])
