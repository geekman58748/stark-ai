# @stark/backend

The Stark API: bills, payments, wallet, limits, voice and the Telegram bot. Python
standard library only: no virtualenv, no `pip install`. Python 3.9 or newer.

The HTTP contract the frontend relies on is [`docs/API.md`](../../docs/API.md). It is
**frozen**: additive changes only. For the full backend state, environment traps and
what to do next, read [`docs/HANDOFF.md`](../../docs/HANDOFF.md).

## Quick start

```sh
cp .env.example .env          # optional, everything works with it empty
bun dev:backend               # from the repo root → http://127.0.0.1:8000
bun smoke                     # in another shell: 50 checks against the running server
```

With no configuration the server is fully offline: payments are dry-run against
captured fixtures, nothing is signed or broadcast, and a deterministic model stands in
for the LLM. Each variable in [`.env.example`](.env.example) switches one piece on.

| Command (from `apps/backend`) | What it does |
|---|---|
| `python3 server.py` | API on port 8000 (no `.env` loading) |
| `python3 smoke_test.py` | 50 end-to-end checks; the server must be running |
| `python3 -m unittest test_agent test_vending test_vtpass test_tg` | unit tests, hermetic, no server needed (`bun run test` from the root) |
| `curl -X POST http://127.0.0.1:8000/v1/_stub/reset` | back to the demo seed; deletes added bills |

Optional: `ffmpeg` on your `PATH` for Telegram voice notes (`brew install ffmpeg`).
Without it the bot asks for text instead of guessing.

## Files

```
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
telegram.py      the Telegram door: webhook auth, identity, wake gate, then the agent
identities.py    channel identity linking and webhook dedupe, in stark.db
audio.py         voice note → 16 kHz mono WAV via ffmpeg
stt.py           speech to text on NEAR AI's Whisper, or an honest refusal
test_tg.py       16 tests: the Telegram door, its gates and the audio path
fixtures/        captured + modeled VTpass responses (see its README)
stark.db         runtime data (receipts, wallet), gitignored
.env.example     every environment variable the server reads
```

## Running it

```sh
bun dev:backend              # from the repo root, loads .env if present
python3 server.py            # or directly, from apps/backend, without .env
```

Both serve http://127.0.0.1:8000.

In another shell, prove it works:

```sh
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
[`docs/API.md`](../../docs/API.md). Bills, limits and `units_left` are in memory, so a
restart returns them to the seed; receipts and the wallet survive.

## Agent

The voice endpoint is the agent. One loop, two models:

```
transcript → model picks a tool → policy gate → sign pay() → book the payment → reply
```

- **The policy gate is not advice in a prompt.** `Agent._pay_bill` checks the per-payment
  cap, the monthly cap, the meter allowlist and the balance before anything is signed or
  charged. A model that ignores every instruction still cannot overspend.
- **Same rules as the contract.** `policy.py` mirrors [`policy.rs`](../contracts/vault/src/policy.rs),
  and a test reads the Rust source and fails if a code or sentence drifts.
- **No key needed.** Without `NEAR_AI_API_KEY` the server uses a deterministic model that
  emits the same tool calls a real one would, so the loop, the tools and the gate are
  the real thing and the tests are hermetic.

```sh
python3 -m unittest test_agent     # 59 tests
python3 -m unittest test_vending   # 44 tests
python3 -m unittest test_vtpass    # 30 tests
python3 smoke_test.py              # 50 checks, server must be running
python3 -m unittest test_tg        # 16 tests: the Telegram door and its gates
```

## Telegram bot

The bot runs the same agent behind the same policy gate. It **refuses everything**
until you give it secrets — an unauthenticated webhook is a wallet anyone on the
internet could talk to:

```sh
# apps/backend/.env
TELEGRAM_BOT_TOKEN=123456:ABC-your-token     # from @BotFather
TELEGRAM_WEBHOOK_SECRET=...                  # openssl rand -hex 32
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
and the NEAR AI model client has never run with a key. See [`HANDOFF.md`](../../docs/HANDOFF.md) §10.

## Bill API (VTpass)

Dry-run by default, so it works with no credentials:

```sh
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

## Vending and receipts

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
sandbox catalogue captured in [`fixtures/`](fixtures/README.md) (see its README):

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

Receipts and the wallet live in `stark.db` (gitignored). `POST /v1/_stub/reset`
wipes it and re-seeds the artboards' six activity entries.
