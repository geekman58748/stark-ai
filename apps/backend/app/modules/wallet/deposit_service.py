"""Adding money: one deposit, two rails, one way to credit it.

| `method` | Rail | The user | Confirmed by |
|---|---|---|---|
| `bank` | Bachs checkout | opens a hosted page: bank transfer, card, or USDT/USDC | `collection.succeeded` webhook, or the money loop reading the checkout |
| `crypto` | NEAR Intents (1Click) | sends the quoted amount of what they hold to a one-off address | the money loop reading `/v0/status` |

Either way the credit is the same three writes, and each is safe to repeat:

1. the wallet and an activity entry, in one statement keyed on the deposit id
   (`UNIQUE (user_id, request_id)` — a second webhook cannot credit twice);
2. the vault's `fund(amount, deposit id)` through the outbox;
3. the deposit row marked `credited`.

The money is spendable the moment step 1 lands: Stark fronts the naira from the
VTpass float and settles the rail afterwards.

A crypto deposit is credited at the rate locked when it was quoted
(`STARK_USDC_NGN_RATE`, naira per USDC — Stark's buying rate), and never for more
than the naira the user asked for.
"""

from __future__ import annotations

import math
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_DOWN, Decimal
from typing import Any, Optional

from app.common.api_error import ApiError
from app.common.clock import Clock
from app.database import neon
from app.modules.bachs.bachs import BachsClient, BachsError
from app.modules.intents import one_click
from app.modules.intents.one_click import OneClickClient, OneClickError
from app.modules.receipt.receipt_repository import ReceiptRepository
from app.modules.vault.vault_service import VaultService

MIN_DEPOSIT_NGN = 100            # Bachs's NGN checkout minimum
MAX_DEPOSIT_NGN = 5_000_000      # Bachs's default single-deposit limit
WINDOW_MINUTES = 60
UNIQUE_VIOLATION = "23505"


@dataclass(frozen=True)
class FundingSettings:
    app_url: Optional[str]
    treasury_account: Optional[str]
    usdc_ngn_rate: Optional[Decimal]


class DepositService:
    def __init__(self, db: neon.Database, receipts: ReceiptRepository, vaults: VaultService,
                 bachs: Optional[BachsClient], one_click_client: OneClickClient,
                 settings: FundingSettings) -> None:
        self.db = db
        self.receipts = receipts
        self.vaults = vaults
        self.bachs = bachs
        self.one_click = one_click_client
        self.settings = settings
        self._tokens: Optional[tuple[float, list[dict[str, Any]]]] = None
        self._tokens_lock = threading.Lock()

    # --- what can be used -----------------------------------------------------

    def methods(self) -> dict[str, bool]:
        return {"bank": self.bachs is not None, "crypto": self._crypto_ready()}

    def crypto_assets(self) -> list[dict[str, Any]]:
        if not self._crypto_ready():
            return []
        return [
            {"asset_id": t["assetId"], "symbol": t["symbol"], "chain": t["blockchain"]}
            for t in self._token_list()
        ]

    def crypto_token(self, asset_id: str) -> Optional[dict[str, Any]]:
        """One listed 1Click token, or None. Withdrawals pay out to the same list."""
        return next((t for t in self._token_list() if t["assetId"] == asset_id), None)

    # --- starting a deposit -----------------------------------------------------

    def start(self, account_id: str, amount_ngn: int, method: str,
              asset_id: Optional[str]) -> dict[str, Any]:
        if not MIN_DEPOSIT_NGN <= amount_ngn <= MAX_DEPOSIT_NGN:
            raise ApiError(400, "bad_amount",
                           f"Add between ₦{MIN_DEPOSIT_NGN:,} and ₦{MAX_DEPOSIT_NGN:,}.")
        if method == "bank":
            return self._start_bank(account_id, amount_ngn)
        if method == "crypto":
            if not asset_id:
                raise ApiError(400, "bad_asset", "Pick what you're paying with.")
            return self._start_crypto(account_id, amount_ngn, asset_id)
        raise ApiError(400, "bad_method", "method must be bank or crypto")

    def _start_bank(self, account_id: str, amount_ngn: int) -> dict[str, Any]:
        if self.bachs is None:
            raise ApiError(501, "not_available",
                           "Adding money by bank or card isn't set up yet. Nothing was taken.")
        deposit_id = f"dep_{uuid.uuid4().hex[:16]}"
        success_url = (f"{self.settings.app_url.rstrip('/')}/wallet/add?deposit={deposit_id}"
                       if self.settings.app_url else None)
        try:
            checkout = self.bachs.create_checkout(
                amount_ngn=amount_ngn, reference=deposit_id,
                metadata={"account_id": account_id, "deposit_id": deposit_id},
                success_url=success_url, expires_in_minutes=WINDOW_MINUTES,
            )
        except BachsError as err:
            raise ApiError(502, "provider_failed",
                           "Couldn't start that payment. Nothing was taken.") from err
        row = self.db.one(
            "INSERT INTO deposits (id, user_id, method, amount_ngn, status, provider_ref,"
            " checkout_url, expires_at, created_at, updated_at)"
            " VALUES ($1, $2, 'bank', $3, 'open', $4, $5, $6, $7, $7) RETURNING *",
            [deposit_id, account_id, amount_ngn, checkout["checkout_id"],
             checkout["checkout_url"], checkout.get("expires_at"), Clock.now_iso()],
        )
        return shape(row)

    def _start_crypto(self, account_id: str, amount_ngn: int, asset_id: str) -> dict[str, Any]:
        if not self._crypto_ready():
            raise ApiError(501, "not_available",
                           "Adding money with crypto isn't set up yet. Nothing was taken.")
        token = self.crypto_token(asset_id)
        if token is None:
            raise ApiError(400, "bad_asset", "That isn't something Stark accepts.")
        rate = self.settings.usdc_ngn_rate
        assert rate is not None and self.settings.treasury_account
        # Round the USDC up, so the credit at the locked rate covers the naira asked.
        usdc_out = math.ceil(Decimal(amount_ngn) / rate * 10 ** one_click.USDC_DECIMALS)
        deadline = (datetime.now(timezone.utc) + timedelta(minutes=WINDOW_MINUTES)) \
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            quoted = self.one_click.quote(
                origin_asset=asset_id, usdc_out=usdc_out,
                recipient=self.settings.treasury_account, deadline=deadline,
            )
        except OneClickError as err:
            raise ApiError(502, "provider_failed",
                           "Couldn't get a price for that right now. Nothing was taken.") \
                from err
        quote = quoted["quote"]
        deposit_id = f"dep_{uuid.uuid4().hex[:16]}"
        row = self.db.one(
            "INSERT INTO deposits (id, user_id, method, amount_ngn, status, provider_ref,"
            " deposit_address, deposit_memo, asset_id, asset_symbol, asset_chain,"
            " amount_in, amount_in_formatted, usdc_out, rate_ngn_per_usdc, expires_at,"
            " created_at, updated_at)"
            " VALUES ($1, $2, 'crypto', $3, 'open', $4, $4, $5, $6, $7, $8, $9, $10, $11,"
            " $12, $13, $14, $14) RETURNING *",
            [deposit_id, account_id, amount_ngn, quote["depositAddress"],
             quote.get("depositMemo"), asset_id, token["symbol"], token["blockchain"],
             quote["amountIn"], quote["amountInFormatted"], str(usdc_out), str(rate),
             quote.get("deadline") or deadline, Clock.now_iso()],
        )
        return shape(row)

    # --- reading ----------------------------------------------------------------

    def recent(self, account_id: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.db.query(
            "SELECT * FROM deposits WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
            [account_id, limit],
        )
        return [shape(row) for row in rows]

    def get(self, account_id: str, deposit_id: str) -> dict[str, Any]:
        """One deposit, checked with its rail first if it is still open."""
        row = self._row(account_id, deposit_id)
        if row["status"] in ("open", "confirming"):
            self._check(row)
            row = self._row(account_id, deposit_id)
        return shape(row)

    def submit_tx(self, account_id: str, deposit_id: str, tx_hash: str) -> dict[str, Any]:
        row = self._row(account_id, deposit_id)
        if row["method"] != "crypto":
            raise ApiError(400, "bad_method", "Only a crypto deposit takes a transaction.")
        try:
            self.one_click.submit_deposit(row["deposit_address"], tx_hash, row["deposit_memo"])
        except OneClickError as err:
            raise ApiError(400, "bad_tx", "That transaction wasn't recognised.") from err
        return self.get(account_id, deposit_id)

    def _row(self, account_id: str, deposit_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM deposits WHERE id = $1 AND user_id = $2",
                          [deposit_id, account_id])
        if row is None:
            raise ApiError(404, "unknown_deposit", "No deposit with that id.")
        return row

    # --- confirming -------------------------------------------------------------

    def on_collection(self, event_type: str, data: dict[str, Any]) -> None:
        """A Bachs collection event. Deposits are matched on our `reference`."""
        reference = data.get("reference")
        if not reference:
            return  # a virtual-account transfer or a checkout we did not create
        row = self.db.one("SELECT * FROM deposits WHERE id = $1", [reference])
        if row is None or row["status"] == "credited":
            return
        status = str(data.get("status") or "").upper()
        if event_type == "collection.succeeded" and status in ("SUCCEEDED", "OVERPAID"):
            self._credit(row, int(row["amount_ngn"]))
        elif event_type == "collection.succeeded" and status == "ACCEPTED":
            self._set_status(row["id"], "confirming", None)
        elif event_type == "collection.failed":
            self._set_status(row["id"], "failed", data.get("reason"))

    def poll_open(self) -> None:
        """The money loop's pass over every deposit still in flight."""
        for row in self.db.query(
            "SELECT * FROM deposits WHERE status IN ('open', 'confirming')"
            " ORDER BY created_at LIMIT 100"
        ):
            self._check(row)

    def _check(self, row: dict[str, Any]) -> None:
        try:
            if row["method"] == "bank":
                self._check_bank(row)
            else:
                self._check_crypto(row)
        except (BachsError, OneClickError):
            return  # the next pass tries again

    def _check_bank(self, row: dict[str, Any]) -> None:
        if self.bachs is None:
            return
        checkout = self.bachs.get_checkout(row["provider_ref"])
        if checkout["status"] == "completed":
            self._credit(row, int(row["amount_ngn"]))
        elif checkout["status"] in ("expired", "cancelled") and row["status"] == "open":
            self._set_status(row["id"], "expired", None)

    def _check_crypto(self, row: dict[str, Any]) -> None:
        report = self.one_click.status(row["deposit_address"], row["deposit_memo"])
        status = report["status"]
        if status == "SUCCESS":
            out = int(report["swapDetails"].get("amountOut") or row["usdc_out"])
            credited = Decimal(out) * Decimal(row["rate_ngn_per_usdc"]) \
                / 10 ** one_click.USDC_DECIMALS
            amount = min(int(credited.to_integral_value(rounding=ROUND_DOWN)),
                         int(row["amount_ngn"]))
            self._credit(row, amount)
        elif status in ("REFUNDED", "FAILED"):
            reason = report["swapDetails"].get("refundReason") or status.lower()
            self._set_status(row["id"], "refunded" if status == "REFUNDED" else "failed",
                             reason)
        elif status == "PENDING_DEPOSIT" and _past(row["expires_at"]):
            self._set_status(row["id"], "expired", None)

    def _credit(self, row: dict[str, Any], amount_ngn: int) -> None:
        crypto = row["method"] == "crypto"
        try:
            self.receipts.record_deposit(row["user_id"], {
                "id": f"rcpt_{uuid.uuid4().hex[:6]}",
                "request_id": row["id"],
                "bill_id": "wallet",
                "bill_label": "Added money",
                "meter": None,
                "amount_ngn": amount_ngn,
                "units": None,
                "token": None,
                "tx_hash": None,
                "status": "received",
                "entry_type": "deposit",
                "source": f"{row['asset_symbol']} on {row['asset_chain']}" if crypto
                else "Bank or card",
                "vendor": "near-intents" if crypto else "bachs",
                "vendor_code": None,
                "vendor_message": None,
                "created_at": Clock.now_iso(),
            }, amount_ngn)
        except neon.DatabaseError as err:
            if err.code != UNIQUE_VIOLATION:
                raise
            # Already credited by the webhook or an earlier pass: fall through so
            # the vault and the row still catch up.
        self.vaults.credit(row["user_id"], amount_ngn, row["id"])
        self.db.query(
            "UPDATE deposits SET status = 'credited', credited_ngn = $2, credited_at = $3,"
            " updated_at = $3 WHERE id = $1 AND status <> 'credited'",
            [row["id"], amount_ngn, Clock.now_iso()],
        )

    def _set_status(self, deposit_id: str, status: str, note: Optional[str]) -> None:
        self.db.query(
            "UPDATE deposits SET status = $2, note = $3, updated_at = $4"
            " WHERE id = $1 AND status <> 'credited'",
            [deposit_id, status, note, Clock.now_iso()],
        )

    # --- plumbing -----------------------------------------------------------------

    def _crypto_ready(self) -> bool:
        return bool(self.settings.treasury_account and self.settings.usdc_ngn_rate)

    def _token_list(self) -> list[dict[str, Any]]:
        """1Click's token list, kept for ten minutes."""
        with self._tokens_lock:
            if self._tokens is not None and time.monotonic() - self._tokens[0] < 600:
                return self._tokens[1]
        try:
            tokens = self.one_click.tokens()
        except OneClickError as err:
            raise ApiError(502, "provider_failed",
                           "Couldn't load what you can pay with right now.") from err
        with self._tokens_lock:
            self._tokens = (time.monotonic(), tokens)
        return tokens


def shape(row: dict[str, Any]) -> dict[str, Any]:
    """The `Deposit` the API returns. `pay` is what the user does next."""
    pay: dict[str, Any]
    if row["method"] == "bank":
        pay = {"checkout_url": row["checkout_url"]}
    else:
        pay = {
            "asset": row["asset_symbol"],
            "chain": row["asset_chain"],
            "amount": row["amount_in_formatted"],
            "address": row["deposit_address"],
            "memo": row["deposit_memo"],
        }
    return {
        "id": row["id"],
        "method": row["method"],
        "amount_ngn": int(row["amount_ngn"]),
        "credited_ngn": int(row["credited_ngn"]) if row.get("credited_ngn") is not None
        else None,
        "status": row["status"],
        "note": row.get("note"),
        "pay": pay,
        "expires_at": row["expires_at"],
        "created_at": row["created_at"],
        "credited_at": row.get("credited_at"),
    }


def _past(iso: Optional[str]) -> bool:
    if not iso:
        return False
    when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return when < datetime.now(timezone.utc)
