# Stark

An AI agent that pays your everyday bills from a crypto balance, within limits you
set, by voice or chat. Starts with Nigerian prepaid electricity; covers airtime,
data, TV, internet and water. Built for **NEAR HACKATHON** (2026-11-01 → 11-14).

- Tracks: `realworld` (lead), `security`, `agents`
- Design source and full project history: the `export/` folder on the Desktop
- **Building the web app or dashboard? Start with [`FRONTEND.md`](FRONTEND.md).** What to
  build, which route backs each screen, and the rules that matter.
- **Working on the backend? Read [`HANDOFF.md`](HANDOFF.md) first.** It has the environment
  traps, what is verified vs guessed, and what to do next.

## Current state

**Nothing is live yet.** The bill API, the vault contract and the agent all exist and
are tested, but every payment is dry-run: no real token has been vended, no transaction
broadcast and no contract deployed. No real AI model has been called.

| Piece | Status |
|---|---|
| API contract | **frozen** — see [`docs/API.md`](docs/API.md) |
| Stub server | working, 50/50 smoke checks |
| App routes | **built** — plans, bill add/edit/delete, limits and wallet, additive to `/v1` |
| VTpass client | written, dry-run verified, 30/30 tests — **live token unproven** |
| Vending (M3) | **wired** — electricity, airtime, data and TV. Dry-run by default, 44 tests |
| Receipts | **persisted** in SQLite: token ↔ tx hash ↔ request_id, survives restart |
| Vault contract | **built** — 38/38 tests, wasm target checks clean, clippy clean. Ledger-only: it does not move tokens yet |
| Agent + LLM | **built (M2)** — tool routing, policy gate, `pay()` signing. 59 tests. Signs but does not broadcast |
| Telegram bot (M4) | **built, fail-closed** — webhook auth, identity linking, dedupe, voice wake gate. 16 tests. Needs `TELEGRAM_BOT_TOKEN` + `TELEGRAM_WEBHOOK_SECRET` to go live |
| Voice (Whisper) | **pipeline built (M4)** — ffmpeg decode + NEAR AI client. Needs `NEAR_AI_API_KEY`; no transcript has ever come back |
| TTS | not started — replies are text; provider unchosen |
| AC telemetry | not started (M6) |

## Run the stub

No dependencies, no virtualenv. Any `python3` works.

```sh
cd backend
python3 server.py            # → http://127.0.0.1:8000
```

In another shell, prove it works:

```sh
cd backend
python3 smoke_test.py        # 50 checks, exits 1 on failure
```

Then try the two calls the app actually makes:

```sh
curl -s http://127.0.0.1:8000/v1/state

curl -s -X POST http://127.0.0.1:8000/v1/payments \
  -H 'Content-Type: application/json' \
  -d '{"bill_id":"bill_home_meter","amount_ngn":5000}'

curl -s -X POST http://127.0.0.1:8000/v1/voice \
  -H 'Content-Type: application/json' \
  -d '{"transcript_hint":"hello stark what's my light bill"}'
```

Mock values match the exported artboards (₦64,200 balance, ₦30,000 monthly cap,
₦23,000 spent / ₦7,000 left, "Home" meter, "Living room TV" on DStv Compact, "My
line" airtime, "4 days left") so screens render with the numbers already in the
design. `/v1/activity` is seeded with the artboards' six entries, including the
declined ₦15,000 attempt and the +₦20,000 bank transfer.

The screens' other routes are live in the same server: `GET /v1/plans`,
`POST`/`PATCH`/`DELETE /v1/bills`, `GET`/`PATCH /v1/limits`, `GET /v1/wallet`, and
`POST /v1/wallet/topup` / `withdraw`. Shapes and error codes are in
[`docs/API.md`](docs/API.md). Bills, limits and `units_left` are in memory, so a
restart returns them to the seed; receipts and the wallet survive.

## Repo layout

```
backend/
  server.py        zero-dependency API stub, `/v1/voice` routed through the agent
  smoke_test.py    50 checks, covers every endpoint and error code
  agent.py         tool schema, tool routing, policy gate, model loop
  policy.py        the vault's rules in Python, same codes and sentences
  near_tx.py       borsh + ed25519 + base58 + RPC: builds and signs pay()
  vault_signer.py  function-call key wiring, dry-run by default
  receipts.py      SQLite receipt store; request_id is the idempotency key
  vending.py       bill kind → VTpass product; amount-priced vs plan-priced
  catalog.py       service ids, plans and prices, read from captured fixtures
  payments.py      record → buy → charge-on-delivery → receipt
  test_agent.py    59 tests: policy parity, RFC 8032 vectors, borsh, the cap gate
  test_vending.py  44 tests: store, idempotent retry, charge-on-delivery, plans
  vtpass.py        VTpass client, dry-run by default
  test_vtpass.py   30 tests, including the CLI wiring
  fixtures/        captured + modeled VTpass responses (see its README)
contracts/
  vault/           NEAR contract: caps, allowlist, owner withdraw
  vault/src/       lib.rs (contract) + policy.rs (pure rules, unit-tested)
docs/
  API.md           the frozen contract — read this first
```

## Agent (M2)

The voice endpoint is the agent. One loop, two models:

```
transcript → model picks a tool → policy gate → sign pay() → book the payment → reply
```

- **The policy gate is not advice in a prompt.** `Agent._pay_bill` checks the per-payment
  cap, the monthly cap, the meter allowlist and the balance before anything is signed or
  charged. A model that ignores every instruction still cannot overspend.
- **Same rules as the contract.** `policy.py` mirrors `contracts/vault/src/policy.rs`,
  and a test reads the Rust source and fails if a code or sentence drifts.
- **No key needed.** Without `NEAR_AI_API_KEY` the server uses a deterministic model that
  emits the same tool calls a real one would, so the loop, the tools and the gate are
  the real thing and the tests are hermetic.

```sh
cd backend
python3 -m unittest test_agent     # 59 tests
python3 -m unittest test_vending   # 44 tests
python3 -m unittest test_vtpass    # 30 tests
python3 smoke_test.py              # 50 checks, server must be running
python3 -m unittest test_tg        # 16 tests: the Telegram door and its gates
```

## Telegram bot (M4)

The bot runs the same agent behind the same policy gate. It **refuses everything**
until you give it secrets — an unauthenticated webhook is a wallet anyone on the
internet could talk to:

```sh
export TELEGRAM_BOT_TOKEN="123456:ABC-your-token"   # from @BotFather
export TELEGRAM_WEBHOOK_SECRET="$(openssl rand -hex 32)"
python3 server.py
```

Then set the webhook so Telegram pushes updates to it, with the same secret:

```sh
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=https://<your-host>/v1/tg/webhook" \
  -d "secret_token=$TELEGRAM_WEBHOOK_SECRET"
```

In Telegram: send `link 482913` with the code shown in the app, then ask by text or
voice note. Voice notes need the word "stark" first — the same rule `/v1/voice`
uses. Without `NEAR_AI_API_KEY` the bot says it cannot hear voice notes rather than
guessing what you said.

To sign `pay()` for real, add a function-call key scoped to the vault and set:

```sh
STARK_SIGNER_KEY=ed25519:<base58 secret>   # the function-call key
STARK_SIGNER_ACCOUNT=agent.testnet
STARK_VAULT_ACCOUNT=vault.testnet
STARK_NETWORK=testnet                      # or mainnet
STARK_BROADCAST=0                          # 1 to actually send
```

With no key the payment is booked without a chain authorisation — the stub's
behaviour. With a key, a signature that cannot be produced **refuses the payment**
rather than charging unaccountably. Broadcasting is off by default, the same way
`vtpass.py` is dry-run by default.

**Honest limits:** the borsh layout has never been round-tripped against a live RPC,
and the NEAR AI model client has never run with a key. See [`HANDOFF.md`](HANDOFF.md) §10.

## Vault contract

```sh
cd contracts/vault
RUSTUP_HOME=/Users/mac/.rustup cargo test                                # 38 tests
RUSTUP_HOME=/Users/mac/.rustup cargo check  --target wasm32-unknown-unknown
RUSTUP_HOME=/Users/mac/.rustup cargo build  --target wasm32-unknown-unknown --release
```

`RUSTUP_HOME` is required here, not optional — the shell's `$HOME` is redirected
and rustup would otherwise find no toolchain. See [`HANDOFF.md`](HANDOFF.md) §1.

**Enforces:** monthly cap, per-payment cap, meter allowlist, owner-only policy
changes, pause, and an owner-withdraw that still works while paused. The spend
counter resets on the first of each calendar month.

**Does not move tokens yet.** `balance_ngn` is an internal ledger. The real
version credits on an NEP-141 `ft_on_transfer` and settles USDC to the treasury —
that is M3. If anyone implies money moves onchain today, they are wrong.

The wasm artifact comes from plain `cargo build --target wasm32-unknown-unknown --release`
(203 KB, verified 2026-10-20) — `cargo-near` is only needed for the ABI JSON and the deploy
convenience, and neither it nor `near` is installed here. Deployment itself is blocked on a
funded testnet account; see section 0 of [`HANDOFF.md`](HANDOFF.md).

## Bill API (VTpass)

Dry-run by default, so it works with no credentials:

```sh
cd backend
python3 vtpass.py variations                       # prepaid | postpaid
python3 vtpass.py verify --meter 04512345678
python3 vtpass.py buy --meter 04512345678 --amount 5000 --phone 08031234567
python3 vtpass.py buy ... --fixture pay_pending.json    # exercise the pending path
python3 -m unittest test_vtpass -v                 # 30 tests
```

Two behaviours the agent depends on:

- **A token only counts when `code == "000"` and `status == "delivered"`.** A `099`/`pending`
  transaction must not be reported as paid — requery it with the same `request_id`.
- **Retries reuse the same `request_id`.** A new id on a retry books a second sale (`019`).

Add `--live` to hit the real API. It needs `VTPASS_ENV`, `VTPASS_USERNAME`,
`VTPASS_PASSWORD` (sandbox default), or the `VTPASS_API_KEY` /
`VTPASS_PUBLIC_KEY` / `VTPASS_SECRET_KEY` trio. Never commit them.

The 13 catalogue fixtures (`services_*.json`, `service-variations_*.json`) are real
captured responses (2026-10-22). The five purchase-response fixtures
(`merchant-verify_ok.json`, `pay_*.json`) are **modeled on the documented shape and have
never been seen live** — replace them with real captures the moment you have credentials.

## Vending and receipts (M3)

A payment runs in this order, and the order is the safety argument:

```
policy check → sign pay() → record the intent → buy → charge → speak the token
```

- **Record before buying.** The receipt exists with a `request_id` and status
  `pending` before the vendor is called. If the process dies mid-purchase, the id
  survives and the purchase is re-queried instead of duplicated — VTpass treats a
  retry with a new id as a second sale (`019`).
- **Charge only on delivery.** `pending` and `failed` never move money. A delivered
  transaction with no token is treated as pending, not success.
- **A retry reuses its request_id.** Paying the same bill for the same amount while a
  purchase is still pending re-queries it rather than buying again.

Dry by default: the request still flows through the VTpass client, but it reads
`fixtures/pay_ok.json`. To vend for real:

```sh
STARK_VENDING=live
VTPASS_ENV=sandbox
VTPASS_USERNAME=... VTPASS_PASSWORD=...
STARK_PHONE=08031234567            # the phone VTpass quotes on the purchase
```

`STARK_VENDING=live` **refuses to start without credentials** — discovering that on
someone's meter is worse than a clean config error.

**What is vendable, and on what evidence.** All of these are confirmed against the
sandbox catalogue captured in `backend/fixtures/` (see its README):

| Kind | Vendor products | Priced by |
|---|---|---|
| electricity | `ikeja-electric` (prepaid) | amount |
| airtime | `mtn`, `airtel`, `glo`, `etisalat` | amount, inside the vendor's own min/max |
| data | `mtn-data`, `airtel-data`, `glo-data`, `etisalat-data` | **plan** |
| tv | `dstv`, `gotv`, `startimes`, `showmax` | **plan** |

A plan is a VTpass variation code (`dstv79` = DStv Compact, ₦7,900) with a fixed
price. Those bills carry `plan` and `plan_price_ngn`, and a payment for any other
amount is refused rather than silently accepted. Water and internet are not wired:
asking for them refuses and charges nothing.

The demo's per-payment cap is ₦10,000 for this reason — a ₦5,000 cap makes the TV
bill impossible to pay.

Receipts and the wallet live in `backend/stark.db` (gitignored). `POST /v1/_stub/reset`
wipes it and re-seeds the artboards' six activity entries.

## Ground rules

- **The contract is frozen.** Additive changes only. Renames or type changes mean
  `/v2`, and they break the frontend for no reason.
- **Money is integer naira** everywhere. No floats.
- **No crypto jargon in user-facing copy.** No "vault", no "USDC", no addresses.
- **No sliders**, anywhere in the app.
- **Never commit secrets.** Keys go in env vars.

## Build order

| # | Milestone | Cutting order if behind |
|---|---|---|
| M0 | Contract frozen, VTpass sandbox confirmed | — |
| M1 | Vault contract + caps | **built (not deployed)** |
| M2 | Agent server, signed `pay()` | never cut |
| M3 | Real token vending, receipts | never cut |
| M4 | Telegram + Whisper voice | 4th |
| M5 | NEAR Intents funding | 3rd |
| M6 | AC telemetry + suggestions | 1st |
| M7 | Frontend wired, demo recorded | — |
