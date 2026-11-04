"""Where Stark's money is, against what it owes — and the loop that keeps it moving.

**Coverage.** Every naira in a user's wallet is a promise Stark must be able to
keep. It is covered by money Stark actually holds:

    owed     = Σ wallet balances
    held     = VTpass float + Bachs NGN balance + treasury USDC × rate
    coverage = held − owed           (must never go negative)

`report()` prints both sides; `python -m app.modules.treasury.treasury_service`
runs it from a shell. Treasury USDC is read through NEAR RPC when a treasury
account is configured.

**The money loop** (`start`) runs every `STARK_MONEY_TICK` seconds (default 30):

1. send vault ops that are still pending (`VaultService.flush`);
2. check open deposits with their rail (catches a missed webhook);
3. send withdrawals whose bank account Bachs has approved;
4. send held crypto withdrawals and follow their swaps;
5. read the float, and refill it if it is low.

Each step is idempotent and isolated: one failing never stops the others.
"""

from __future__ import annotations

import logging
import threading
from decimal import Decimal
from typing import Any, Callable, Optional

from app.database import neon
from app.modules.bachs.bachs import BachsClient, BachsError
from app.modules.chain import near_tx
from app.modules.intents import one_click
from app.modules.liquidity.float_service import FloatService
from app.modules.vault.vault_service import VaultService
from app.modules.vending.vtpass import VtpassError
from app.modules.wallet.deposit_service import DepositService
from app.modules.wallet.crypto_withdrawal_service import CryptoWithdrawalService
from app.modules.wallet.withdrawal_service import WithdrawalService

log = logging.getLogger("stark.treasury")
USDC_CONTRACT = one_click.USDC_NEAR.split(":", 1)[1]


class TreasuryService:
    def __init__(self, db: neon.Database, vaults: VaultService, deposits: DepositService,
                 withdrawals: WithdrawalService, crypto_withdrawals: CryptoWithdrawalService,
                 floats: FloatService,
                 bachs: Optional[BachsClient], treasury_account: Optional[str],
                 usdc_ngn_rate: Optional[Decimal],
                 mainnet_rpc: near_tx.NearRpc) -> None:
        self.db = db
        self.vaults = vaults
        self.deposits = deposits
        self.withdrawals = withdrawals
        self.crypto_withdrawals = crypto_withdrawals
        self.floats = floats
        self.bachs = bachs
        self.treasury_account = treasury_account
        self.usdc_ngn_rate = usdc_ngn_rate
        self.mainnet_rpc = mainnet_rpc

    def report(self) -> dict[str, Any]:
        owed = int(self.db.value("SELECT COALESCE(SUM(balance_ngn), 0) FROM wallets") or 0)
        held: dict[str, Optional[int]] = {
            "vtpass_float_ngn": _read(lambda: self.floats.balance(fresh=True)),
            "vtpass_reserved_ngn": self.floats.reserved(),
            "bachs_ngn": _read(self.bachs.ngn_balance) if self.bachs else None,
            "treasury_usdc_as_ngn": _read(self._treasury_usdc_as_ngn),
        }
        known = sum(v for k, v in held.items() if v is not None and k != "vtpass_reserved_ngn")
        open_refill = self.db.one(
            "SELECT id, amount_ngn, status FROM float_refills"
            " WHERE status IN ('requested', 'sent', 'manual') ORDER BY created_at DESC LIMIT 1"
        )
        stuck_ops = int(self.db.value(
            "SELECT COUNT(*) FROM chain_ops WHERE status <> 'done'"
        ) or 0)
        return {
            "owed_to_users_ngn": owed,
            "held": held,
            "coverage_ngn": known - held["vtpass_reserved_ngn"] - owed,
            "open_refill": open_refill,
            "unsettled_vault_ops": stuck_ops,
        }

    def _treasury_usdc_as_ngn(self) -> Optional[int]:
        if not (self.treasury_account and self.usdc_ngn_rate):
            return None
        raw = self.mainnet_rpc.view(USDC_CONTRACT, "ft_balance_of",
                                    {"account_id": self.treasury_account})
        usdc = Decimal(str(raw)) / 10 ** one_click.USDC_DECIMALS
        return int(usdc * self.usdc_ngn_rate)

    # --- the loop -------------------------------------------------------------

    def tick(self) -> None:
        for step in (self.vaults.flush, self.deposits.poll_open,
                     self.withdrawals.advance_reviewing, self.crypto_withdrawals.advance,
                     self.floats.check_level):
            try:
                step()
            except Exception:  # one rail being down must not stop the others
                log.exception("money loop step %s failed", step.__name__)

    def start(self, tick_seconds: int) -> threading.Event:
        stop = threading.Event()

        def run() -> None:
            while not stop.wait(tick_seconds):
                self.tick()

        threading.Thread(target=run, daemon=True, name="money").start()
        return stop


def _read(read: Callable[[], Optional[int]]) -> Optional[int]:
    """A balance that could not be read is unknown, not zero."""
    try:
        return read()
    except (BachsError, VtpassError, near_tx.NearRpcError) as err:
        log.warning("balance unreadable: %s", err)
        return None


def _main() -> None:  # pragma: no cover - operator CLI
    import json

    from app.app_module import AppModule

    print(json.dumps(AppModule.from_env().treasury.report(), indent=2, default=str))


if __name__ == "__main__":  # pragma: no cover
    _main()
