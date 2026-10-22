"""Signs `pay()` with a scoped function-call key — and broadcasts only when told to.

The owner adds a function-call access key to the agent's account, allowed **only**
to call `pay` on the vault, with a gas allowance and no attached deposit. That key
cannot withdraw, cannot change the policy and cannot touch any other contract. If
it leaks, the worst it can do is spend inside the caps — which is the whole design
argument for the `security` track.

Dry by default, exactly like `vtpass.py`: a signature is built and verified, but
nothing is sent. Set `STARK_BROADCAST=1` to actually broadcast.

Configuration (env only, never commit any of it):

| Variable | Meaning |
|---|---|
| `STARK_SIGNER_KEY` | `ed25519:<base58>` secret, or hex. The function-call key. |
| `STARK_SIGNER_ACCOUNT` | account that holds the key, e.g. `agent.testnet` |
| `STARK_VAULT_ACCOUNT` | the vault contract, e.g. `vault.testnet` |
| `STARK_NETWORK` | `testnet` (default) or `mainnet` |
| `STARK_BROADCAST` | `1` to send the transaction |

With no key configured this returns `None`, and payments are booked without a
chain authorisation — the stub's behaviour. Fail closed: if a signer *is*
configured and the signature cannot be produced, the payment is refused rather
than charged unaccountably (see `agent.Agent._pay_bill`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

import near_tx


@dataclass
class VaultSigner:
    key: near_tx.KeyPair
    signer_id: str
    receiver_id: str
    rpc: near_tx.NearRpc
    broadcast: bool = False

    def sign_pay(self, meter: str, amount_ngn: int) -> dict:
        """Build `pay(meter, amount_ngn)`, sign it, and maybe send it."""
        context = near_tx.fetch_signing_context(
            self.rpc,
            signer_id=self.signer_id,
            receiver_id=self.receiver_id,
            key=self.key,
        )
        signed = near_tx.sign_pay(
            key=self.key,
            signer_id=self.signer_id,
            receiver_id=self.receiver_id,
            nonce=context.nonce,
            block_hash=context.block_hash,
            meter=meter,
            amount_ngn=amount_ngn,
        )
        summary = signed.summary()
        summary.update({"signed": True, "broadcast": self.broadcast})

        if self.broadcast:
            outcome = self.rpc.broadcast(signed)
            summary["outcome"] = (outcome.get("status") or {}).get("SuccessValue", "sent")
        return summary


def signer_from_env(env: Mapping[str, str] | None = None) -> VaultSigner | None:
    """Build a signer from the environment, or `None` when none is configured.

    Reads config only — no network, so importing the server stays offline-safe.
    """
    source = os.environ if env is None else env
    secret = source.get("STARK_SIGNER_KEY")
    signer_id = source.get("STARK_SIGNER_ACCOUNT")
    vault = source.get("STARK_VAULT_ACCOUNT")
    if not (secret and signer_id and vault):
        return None

    network = (source.get("STARK_NETWORK") or "testnet").strip().lower()
    if network not in ("testnet", "mainnet"):
        raise ValueError("STARK_NETWORK must be testnet or mainnet")

    return VaultSigner(
        key=near_tx.KeyPair.from_string(secret),
        signer_id=signer_id,
        receiver_id=vault,
        rpc=near_tx.NearRpc(
            near_tx.MAINNET_RPC if network == "mainnet" else near_tx.TESTNET_RPC
        ),
        broadcast=(source.get("STARK_BROADCAST") or "").strip().lower()
        in ("1", "true", "yes"),
    )
