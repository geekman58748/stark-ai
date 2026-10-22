"""The receipt store — SQLite, stdlib only.

Two things live here that matter more than the storage itself:

1. **`request_id` is the idempotency key.** VTpass books a second sale if the same
   purchase is retried with a new id (code `019`). A receipt therefore stores its
   `request_id` from the moment it is created, and a retry of the same intent finds
   that row and reuses the id. `find_pending()` is how the payment path does it.
2. **The wallet is persisted next to the receipts.** Otherwise a restart would keep
   the history but forget the balance, and the two would disagree — which is exactly
   the kind of bug that makes a demo lie.

Money is integer naira. Units are a float because the tariff is fractional, and
units are not money.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_DB = Path(__file__).parent / "stark.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS receipts (
    id            TEXT PRIMARY KEY,
    request_id    TEXT NOT NULL UNIQUE,
    bill_id       TEXT NOT NULL,
    bill_label    TEXT NOT NULL,
    meter         TEXT,
    amount_ngn    INTEGER NOT NULL,
    units         REAL,
    token         TEXT,
    tx_hash       TEXT,
    status        TEXT NOT NULL,
    entry_type    TEXT,
    source        TEXT,
    vendor        TEXT,
    vendor_code   TEXT,
    vendor_message TEXT,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS receipts_created ON receipts (created_at DESC);
CREATE INDEX IF NOT EXISTS receipts_pending ON receipts (bill_id, amount_ngn, status);

CREATE TABLE IF NOT EXISTS wallet (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    balance_ngn INTEGER NOT NULL,
    spent_ngn   INTEGER NOT NULL
);
"""


RECEIPT_COLUMNS = (
    "id", "request_id", "bill_id", "bill_label", "meter", "amount_ngn",
    "units", "token", "tx_hash", "status", "entry_type", "source",
    "vendor", "vendor_code", "vendor_message", "created_at",
)


class ReceiptStore:
    def __init__(self, path: str | Path = DEFAULT_DB):
        self.path = str(path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.executescript(SCHEMA)
            # Additive columns for databases created before 2026-10-22.
            existing = {row["name"] for row in self._conn.execute("PRAGMA table_info(receipts)")}
            for column in ("entry_type", "source"):
                if column not in existing:
                    self._conn.execute(f"ALTER TABLE receipts ADD COLUMN {column} TEXT")

    # --- receipts ------------------------------------------------------------

    def _insert_locked(self, receipt: dict[str, Any]) -> None:
        values = [receipt.get(column) for column in RECEIPT_COLUMNS]
        self._conn.execute(
            f"INSERT INTO receipts ({', '.join(RECEIPT_COLUMNS)}) "
            f"VALUES ({', '.join('?' for _ in RECEIPT_COLUMNS)})",
            values,
        )

    def _set_wallet_locked(self, balance_ngn: int, spent_ngn: int) -> None:
        self._conn.execute(
            "INSERT INTO wallet (id, balance_ngn, spent_ngn) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET balance_ngn = excluded.balance_ngn, "
            "spent_ngn = excluded.spent_ngn",
            (balance_ngn, spent_ngn),
        )

    def create(self, receipt: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._conn:
            self._insert_locked(receipt)
        return self.get(receipt["id"])

    def update(self, receipt_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {
            "units", "token", "tx_hash", "status", "vendor", "vendor_code",
            "vendor_message",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"cannot update {sorted(unknown)}")
        if not fields:
            return self.get(receipt_id)
        assignments = ", ".join(f"{name} = ?" for name in fields)
        with self._lock, self._conn:
            self._conn.execute(
                f"UPDATE receipts SET {assignments} WHERE id = ?",
                [*fields.values(), receipt_id],
            )
        return self.get(receipt_id)

    def get(self, receipt_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM receipts WHERE id = ?", (receipt_id,)
            ).fetchone()
        return _row(row)

    def by_request_id(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM receipts WHERE request_id = ?", (request_id,)
            ).fetchone()
        return _row(row)

    def has_pending(self, bill_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM receipts WHERE bill_id = ? AND status = 'pending' LIMIT 1",
                (bill_id,),
            ).fetchone()
        return row is not None

    def find_pending(self, bill_id: str, amount_ngn: int) -> dict[str, Any] | None:
        """The newest unfinished purchase for this exact intent.

        A retry must reuse its `request_id`, or VTpass books a duplicate sale.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM receipts WHERE bill_id = ? AND amount_ngn = ? "
                "AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
                (bill_id, amount_ngn),
            ).fetchone()
        return _row(row)

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM receipts ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row(row) for row in rows]

    def count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0])

    # --- wallet --------------------------------------------------------------

    def wallet(self) -> dict[str, int] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM wallet WHERE id = 1").fetchone()
        if row is None:
            return None
        return {"balance_ngn": int(row["balance_ngn"]), "spent_ngn": int(row["spent_ngn"])}

    def set_wallet(self, balance_ngn: int, spent_ngn: int) -> None:
        with self._lock, self._conn:
            self._set_wallet_locked(balance_ngn, spent_ngn)

    def record_deposit(
        self, receipt: dict[str, Any], amount_ngn: int
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """Insert the activity entry and credit the wallet in one transaction."""
        with self._lock, self._conn:
            self._insert_locked(receipt)
            row = self._conn.execute(
                "SELECT balance_ngn, spent_ngn FROM wallet WHERE id = 1"
            ).fetchone()
            balance = (int(row["balance_ngn"]) if row else 0) + amount_ngn
            spent = int(row["spent_ngn"]) if row else 0
            self._set_wallet_locked(balance, spent)
        return self.get(receipt["id"]), self.wallet()  # type: ignore[return-value]

    def record_withdrawal(
        self, receipt: dict[str, Any], amount_ngn: int
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """Insert the activity entry and debit the wallet, or raise if short."""
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT balance_ngn, spent_ngn FROM wallet WHERE id = 1"
            ).fetchone()
            balance = int(row["balance_ngn"]) if row else 0
            spent = int(row["spent_ngn"]) if row else 0
            if amount_ngn > balance:
                raise ValueError("insufficient_balance")
            self._insert_locked(receipt)
            self._set_wallet_locked(balance - amount_ngn, spent)
        return self.get(receipt["id"]), self.wallet()  # type: ignore[return-value]

    def added_this_month(self) -> int:
        """Deposits that landed since the first of the current UTC month."""
        month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(amount_ngn), 0) FROM receipts "
                "WHERE entry_type = 'deposit' AND status = 'received' "
                "AND created_at >= ?",
                (month_start,),
            ).fetchone()
        return int(row[0]) if row else 0

    def charge(self, amount_ngn: int) -> dict[str, int]:
        """Move money from balance to spend, atomically.

        Raises `ValueError` if the balance moved and can no longer cover it — the
        caller must not book a delivery it cannot pay for.
        """
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT balance_ngn, spent_ngn FROM wallet WHERE id = 1"
            ).fetchone()
            balance = int(row["balance_ngn"]) if row else 0
            spent = int(row["spent_ngn"]) if row else 0
            if amount_ngn > balance:
                raise ValueError("insufficient_balance")
            balance -= amount_ngn
            spent += amount_ngn
            self._conn.execute(
                "INSERT INTO wallet (id, balance_ngn, spent_ngn) VALUES (1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET balance_ngn = excluded.balance_ngn, "
                "spent_ngn = excluded.spent_ngn",
                (balance, spent),
            )
        return {"balance_ngn": balance, "spent_ngn": spent}

    # --- test / demo seam ----------------------------------------------------

    def replace_all(self, receipts: Iterable[dict[str, Any]], *,
                    balance_ngn: int, spent_ngn: int) -> None:
        """Used by the stub-only reset route. Not part of the product."""
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM receipts")
        for receipt in receipts:
            self.create(receipt)
        self.set_wallet(balance_ngn, spent_ngn)

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def api_shape(receipt: dict[str, Any]) -> dict[str, Any]:
    """The frozen `Receipt` shape, plus the additive fields the UI may ignore."""
    return {
        "id": receipt["id"],
        "bill_id": receipt["bill_id"],
        "bill_label": receipt["bill_label"],
        "amount_ngn": receipt["amount_ngn"],
        "units": receipt["units"],
        "token": receipt["token"],
        "tx_hash": receipt["tx_hash"],
        "created_at": receipt["created_at"],
        # Additive (2026-10-22): a pending purchase is not a completed one.
        "status": receipt["status"],
        "request_id": receipt["request_id"],
        # Additive (2026-10-22): `type` is `bill`, `autotopup` or `deposit`;
        # `source` is where the user asked for it (Telegram, wall phone, bank).
        # Live payments predate this column, so they default to `bill`.
        "type": receipt.get("entry_type") or "bill",
        "source": receipt.get("source"),
    }
