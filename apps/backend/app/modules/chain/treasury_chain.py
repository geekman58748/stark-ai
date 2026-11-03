"""The treasury's hot key: sends USDC on NEAR mainnet, and nothing else Stark asks of it.

A crypto withdrawal is paid by moving the treasury's USDC into a 1Click deposit
address (`wallet/crypto_withdrawal_service.py`). `ft_transfer` must attach one
yoctoNEAR, which a function-call key cannot do, so `STARK_TREASURY_KEY` is a
**full-access key on the treasury account**. That is the risk this design accepts,
and why the service caps every withdrawal and each day's total before it signs.

One transaction, two actions, both on the USDC contract:

1. `storage_deposit(account_id=<deposit address>, registration_only=true)` — a
   1Click deposit address is a fresh implicit account; without storage the
   transfer fails. Already registered → the deposit is refunded.
2. `ft_transfer(receiver_id=<deposit address>, amount=<usdc>)`.

`sign` and `send` are separate on purpose: the caller stores the signed bytes
before broadcasting them, so a crash or a timeout is retried with the *same*
transaction, which the chain will only ever execute once.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Mapping, Optional

from app.modules.chain import near_tx
from app.modules.intents import one_click

USDC_CONTRACT = one_click.USDC_NEAR.split(":", 1)[1]
STORAGE_DEPOSIT_YOCTO = 1_250_000_000_000_000_000_000  # 0.00125 NEAR, NEP-145 minimum
ONE_YOCTO = 1
GAS_PER_ACTION = 30_000_000_000_000  # 30 Tgas


@dataclass(frozen=True)
class SignedTransfer:
    encoded: str        # base64 borsh, what the RPC accepts
    tx_hash: str        # base58, what explorers and `tx` status take


class TreasuryChain:
    def __init__(self, *, rpc: near_tx.NearRpc, account_id: str,
                 key: near_tx.KeyPair) -> None:
        self.rpc = rpc
        self.account_id = account_id
        self.key = key
        self._lock = threading.Lock()
        self._next_nonce = 0

    def sign_usdc_transfer(self, receiver_id: str, amount: int) -> SignedTransfer:
        actions = [
            near_tx.function_call_action(
                "storage_deposit",
                near_tx.json_args({"account_id": receiver_id, "registration_only": True}),
                gas=GAS_PER_ACTION, deposit=STORAGE_DEPOSIT_YOCTO,
            ),
            near_tx.function_call_action(
                "ft_transfer",
                near_tx.json_args({"receiver_id": receiver_id, "amount": str(amount),
                                   "memo": "Stark withdrawal"}),
                gas=GAS_PER_ACTION, deposit=ONE_YOCTO,
            ),
        ]
        with self._lock:
            context = near_tx.fetch_signing_context(
                self.rpc, signer_id=self.account_id, receiver_id=USDC_CONTRACT, key=self.key
            )
            nonce = max(context.nonce, self._next_nonce)
            self._next_nonce = nonce + 1
        signed = near_tx.sign_transaction(
            key=self.key, signer_id=self.account_id, receiver_id=USDC_CONTRACT,
            nonce=nonce, block_hash=context.block_hash, actions=actions,
        )
        return SignedTransfer(signed.base64, near_tx.b58encode(signed.tx_hash))

    def send(self, transfer: SignedTransfer) -> None:
        """Broadcast and wait. Raises `ContractRefused` if the transfer itself failed."""
        near_tx.success_value(self.rpc.broadcast_base64(transfer.encoded))

    def outcome(self, transfer: SignedTransfer) -> Optional[dict]:
        return self.rpc.tx_status(transfer.tx_hash, self.account_id)


def treasury_from_env(env: Optional[Mapping[str, str]] = None) -> Optional[TreasuryChain]:
    """None unless both the treasury account and its key are set (crypto payouts off)."""
    source = os.environ if env is None else env
    account_id = (source.get("STARK_TREASURY_NEAR_ACCOUNT") or "").strip()
    key = (source.get("STARK_TREASURY_KEY") or "").strip()
    if not key:
        return None
    if not account_id:
        raise ValueError("STARK_TREASURY_KEY needs STARK_TREASURY_NEAR_ACCOUNT")
    return TreasuryChain(rpc=near_tx.NearRpc(near_tx.MAINNET_RPC), account_id=account_id,
                         key=near_tx.KeyPair.from_string(key))
