# @stark/contracts

NEAR smart contracts, in Rust. Today there is one: [`vault/`](vault), which holds a
user's spending policy and is the account the agent's `pay()` calls are signed against.

## Setup

Not needed for the web app, the dashboard or the backend; skip this unless you are
changing the contract.

```sh
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh   # once
rustup target add wasm32-unknown-unknown
```

## Commands

From the repo root:

| Command | What it does |
|---|---|
| `pnpm --filter @stark/contracts contract:test` | 38 unit tests on the host |
| `pnpm --filter @stark/contracts contract:check` | type-check the wasm target |
| `pnpm --filter @stark/contracts contract:build` | release wasm → `vault/target/wasm32-unknown-unknown/release/stark_vault.wasm` |

Or with cargo directly from `vault/`: `cargo test`, `cargo build --target wasm32-unknown-unknown --release`.

These are deliberately not turbo tasks, so `pnpm test` and `pnpm build` work without a
Rust toolchain.

If cargo reports no toolchain although rustup is installed, your shell's `$HOME` is
probably redirected; set `RUSTUP_HOME` to the real `~/.rustup`. See
[`docs/HANDOFF.md`](../../docs/HANDOFF.md) §1.

## The vault

**Enforces:** monthly cap, per-payment cap, meter allowlist, owner-only policy
changes, pause, and an owner-withdraw that still works while paused. The spend
counter resets on the first of each calendar month.

**Does not move tokens yet.** `balance_ngn` is an internal ledger. The real
version credits on an NEP-141 `ft_on_transfer` and settles USDC to the treasury.
If anyone implies money moves onchain today, they are wrong.

```
vault/src/policy.rs   pure rules, no near-sdk, unit-tested
vault/src/lib.rs      contract wrapper, env-based tests
```

**`policy.rs` has a Python twin.** [`apps/backend/policy.py`](../backend/policy.py)
mirrors its error codes and sentences, and a backend test reads this Rust source and
fails if they drift. Change both together; `pnpm test` will tell you if you didn't.

The wasm comes from plain `cargo build` (203 KB, verified 2026-10-20). `cargo-near` is
only needed for the ABI JSON and deploy convenience. Deployment is blocked on a funded
testnet account; see [`docs/HANDOFF.md`](../../docs/HANDOFF.md) §0.
