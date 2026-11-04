"""Withdrawing to a bank, through Bachs payouts.

    resolve the account name → hold the money → Bachs reviews the destination
    → payout → `payout.paid` (done) or `payout.failed` (money comes back)

The money leaves the balance the moment the withdrawal is asked for (one
statement: debit plus the activity entry), and the vault is debited with the same
reference. Holding it first is what stops a user spending money that is already on
its way to their bank.

Bachs pays only destinations that have passed its review (`is_usable`). A new bank
account starts `pending_review`, so a first withdrawal to it waits as `reviewing`
until the money loop sees it approved; a rejected destination returns the money.
A saved account is reused, so later withdrawals to it go straight out.

Returning money is the mirror image of taking it: a credit keyed `<withdrawal>-r`,
and a vault `fund` with the same reference, so a repeated failure event returns it
once.

`hold`, `mark_paid` and `give_back` are the ledger every withdrawal shares; a
crypto payout (`crypto_withdrawal_service.py`) uses them too, so both methods
take and return money by exactly the same rules.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from app.common.api_error import ApiError
from app.common.clock import Clock
from app.database import neon
from app.modules.bachs.bachs import BachsClient, BachsError
from app.modules.receipt.receipt_repository import ReceiptRepository
from app.modules.vault.vault_service import VaultService

MIN_WITHDRAWAL_NGN = 100
UNIQUE_VIOLATION = "23505"


class WithdrawalService:
    def __init__(self, db: neon.Database, receipts: ReceiptRepository, vaults: VaultService,
                 bachs: Optional[BachsClient]) -> None:
        self.db = db
        self.receipts = receipts
        self.vaults = vaults
        self.bachs = bachs

    # --- helping the user fill the form -----------------------------------------

    def banks(self) -> list[dict[str, str]]:
        return self._bachs().banks()

    def resolve(self, bank_code: str, account_number: str) -> dict[str, Any]:
        _check_account_number(account_number)
        try:
            resolved = self._bachs().resolve_account(bank_code, account_number)
        except BachsError as err:
            raise ApiError(502, "provider_failed", "Couldn't check that account.") from err
        if not resolved.get("resolved"):
            raise ApiError(400, "bad_account",
                           "That account number doesn't match the bank you picked.")
        return {"account_name": resolved["account_name"], "account_number": account_number,
                "bank_code": bank_code}

    # --- the withdrawal -----------------------------------------------------------

    def request(self, account_id: str, amount_ngn: int, bank_code: str,
                account_number: str) -> dict[str, Any]:
        bachs = self._bachs()
        if amount_ngn < MIN_WITHDRAWAL_NGN:
            raise ApiError(400, "bad_amount",
                           f"Withdraw at least ₦{MIN_WITHDRAWAL_NGN:,}.")
        account = self.resolve(bank_code, account_number)
        destination = self._destination(account_id, bachs, account)

        withdrawal_id = f"wd_{uuid.uuid4().hex[:16]}"
        receipt_id = self.hold(
            account_id, withdrawal_id, amount_ngn, label=f"To {account['account_name']}",
            source=f"{destination['bank_name']} ····{account_number[-4:]}", vendor="bachs",
        )
        now = Clock.now_iso()
        self.db.query(
            "INSERT INTO withdrawals (id, user_id, method, amount_ngn, destination_id,"
            " receipt_id, status, created_at, updated_at)"
            " VALUES ($1, $2, 'bank', $3, $4, $5, 'reviewing', $6, $6)",
            [withdrawal_id, account_id, amount_ngn, destination["destination_id"],
             receipt_id, now],
        )
        self.vaults.debit(account_id, amount_ngn, withdrawal_id)
        self._advance(self._row(withdrawal_id))
        return shape(self._row(withdrawal_id))

    def hold(self, account_id: str, withdrawal_id: str, amount_ngn: int, *, label: str,
             source: str, vendor: str) -> str:
        """Take the money out of the balance before it is sent anywhere.

        One statement debits the wallet and writes the activity entry, or refuses if
        the balance is short. Returns the entry's id. The caller then mirrors the
        debit into the vault with the withdrawal id as the reference.
        """
        try:
            receipt, _ = self.receipts.record_withdrawal(account_id, {
                "id": f"rcpt_{uuid.uuid4().hex[:6]}",
                "request_id": withdrawal_id,
                "bill_id": "wallet",
                "bill_label": label,
                "meter": None,
                "amount_ngn": amount_ngn,
                "units": None,
                "token": None,
                "tx_hash": None,
                "status": "processing",
                "entry_type": "withdrawal",
                "source": source,
                "vendor": vendor,
                "vendor_code": None,
                "vendor_message": None,
                "created_at": Clock.now_iso(),
            }, amount_ngn)
        except ValueError:
            raise ApiError(409, "insufficient_balance",
                           "There isn't that much in your wallet.") from None
        return receipt["id"]

    def recent(self, account_id: str, limit: int = 10) -> list[dict[str, Any]]:
        return [shape(row) for row in self.db.query(
            "SELECT * FROM withdrawals WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
            [account_id, limit],
        )]

    # --- moving it along ------------------------------------------------------------

    def advance_reviewing(self) -> None:
        """The money loop's pass: send what Bachs has approved, return what it refused."""
        for row in self.db.query(
            "SELECT * FROM withdrawals WHERE method = 'bank' AND status = 'reviewing'"
            " ORDER BY created_at LIMIT 50"
        ):
            self._advance(row)

    def _advance(self, row: dict[str, Any]) -> None:
        assert self.bachs is not None
        try:
            destination = self.bachs.get_destination(row["destination_id"])
        except BachsError:
            return
        if destination["status"] == "rejected":
            self.give_back(row, destination.get("status_reason") or "bank account refused")
            return
        if not destination.get("is_usable"):
            return
        try:
            payout = self.bachs.create_payout(
                destination=row["destination_id"], amount_ngn=int(row["amount_ngn"]),
                reference=row["id"], narration="Stark",
            )
        except BachsError as err:
            if err.status in (0, 429) or err.status >= 500:
                return  # transient: the next pass sends it with the same reference
            self.give_back(row, err.message)
            return
        self._set(row["id"], "processing", payout["id"], None)

    def on_payout(self, reference: str, paid: bool) -> bool:
        """A payout webhook for one of ours. False if it isn't a withdrawal."""
        row = self.db.one("SELECT * FROM withdrawals WHERE id = $1 AND method = 'bank'",
                          [reference])
        if row is None:
            return False
        if paid:
            if row["status"] != "paid":
                self.mark_paid(row)
        else:
            self.give_back(row, "the bank transfer failed")
        return True

    def mark_paid(self, row: dict[str, Any]) -> None:
        self._set(row["id"], "paid", None, None)
        self.receipts.update(row["user_id"], row["receipt_id"], status="sent")

    def give_back(self, row: dict[str, Any], reason: str) -> None:
        """Return a withdrawal's money to the balance, once, and to the vault with it."""
        if row["status"] == "returned":
            return
        reference = f"{row['id']}-r"
        amount = int(row["amount_ngn"])
        try:
            self.receipts.record_deposit(row["user_id"], {
                "id": f"rcpt_{uuid.uuid4().hex[:6]}",
                "request_id": reference,
                "bill_id": "wallet",
                "bill_label": "Withdrawal returned",
                "meter": None,
                "amount_ngn": amount,
                "units": None,
                "token": None,
                "tx_hash": None,
                "status": "received",
                "entry_type": "deposit",
                "source": "Returned from bank" if row["method"] == "bank"
                else f"Returned, not sent as {row['asset_symbol']}",
                "vendor": "bachs" if row["method"] == "bank" else "near-intents",
                "vendor_code": None,
                "vendor_message": reason[:200],
                "created_at": Clock.now_iso(),
            }, amount)
        except neon.DatabaseError as err:
            if err.code != UNIQUE_VIOLATION:
                raise
        self.receipts.update(row["user_id"], row["receipt_id"], status="failed",
                             vendor_message=reason[:200])
        self.vaults.credit(row["user_id"], amount, reference)
        self._set(row["id"], "returned", None, reason)

    # --- plumbing -----------------------------------------------------------------------

    def _destination(self, account_id: str, bachs: BachsClient,
                     account: dict[str, Any]) -> dict[str, Any]:
        """The Bachs destination for this bank account, saved after the first use."""
        saved = self.db.one(
            "SELECT * FROM payout_destinations WHERE user_id = $1 AND bank_code = $2"
            " AND account_number = $3",
            [account_id, account["bank_code"], account["account_number"]],
        )
        if saved is not None:
            return saved
        try:
            created = bachs.create_destination(
                bank_code=account["bank_code"], account_number=account["account_number"],
                name=account["account_name"], metadata={"account_id": account_id},
            )
        except BachsError as err:
            raise ApiError(502, "provider_failed",
                           "Couldn't save that bank account. Nothing was taken.") from err
        return self.db.one(
            "INSERT INTO payout_destinations (user_id, bank_code, account_number,"
            " destination_id, account_name, bank_name, created_at)"
            " VALUES ($1, $2, $3, $4, $5, $6, $7)"
            " ON CONFLICT (user_id, bank_code, account_number)"
            " DO UPDATE SET destination_id = EXCLUDED.destination_id RETURNING *",
            [account_id, account["bank_code"], account["account_number"], created["id"],
             created.get("account_name") or account["account_name"],
             created.get("bank_name") or account["bank_code"], Clock.now_iso()],
        )  # type: ignore[return-value]

    def _bachs(self) -> BachsClient:
        if self.bachs is None:
            raise ApiError(501, "not_available",
                           "Withdrawing to a bank isn't set up yet. Nothing was taken.")
        return self.bachs

    def _row(self, withdrawal_id: str) -> dict[str, Any]:
        return self.db.one("SELECT * FROM withdrawals WHERE id = $1",
                           [withdrawal_id])  # type: ignore[return-value]

    def _set(self, withdrawal_id: str, status: str, payout_id: Optional[str],
             note: Optional[str]) -> None:
        self.db.query(
            "UPDATE withdrawals SET status = $2, payout_id = COALESCE($3, payout_id),"
            " note = $4, updated_at = $5 WHERE id = $1",
            [withdrawal_id, status, payout_id, note, Clock.now_iso()],
        )


def _check_account_number(account_number: str) -> None:
    if not (account_number.isdigit() and len(account_number) == 10):
        raise ApiError(400, "bad_account", "A Nigerian account number has 10 digits.")


def shape(row: dict[str, Any]) -> dict[str, Any]:
    """The `Withdrawal` the API returns. `crypto` is set only for a crypto payout."""
    crypto = None
    if row["method"] == "crypto":
        crypto = {
            "asset": row["asset_symbol"],
            "chain": row["asset_chain"],
            "address": row["address"],
            "amount": row["amount_out_formatted"],
            "tx_hash": row["tx_hash"],
        }
    return {
        "id": row["id"],
        "method": row["method"],
        "amount_ngn": int(row["amount_ngn"]),
        "status": row["status"],
        "note": row.get("note"),
        "crypto": crypto,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
