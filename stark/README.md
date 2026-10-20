# Stark

An AI agent that pays your everyday bills from a crypto balance, within limits you
set, by voice or chat. Starts with Nigerian prepaid electricity; covers airtime,
data, TV, internet and water. Built for **NEAR HACKATHON** (2026-11-01 → 11-14).

- Tracks: `realworld` (lead), `security`, `agents`
- Design source and full project history: the `export/` folder on the Desktop
- **Picking this up fresh? Read [`HANDOFF.md`](HANDOFF.md) first.** It has the environment
  traps, what is verified vs guessed, and what to do next.

## Current state

**Nothing is real yet.** This repo holds the backend contract and a mock server so
the frontend can be built in parallel. No chain, no bill API, no AI.

| Piece | Status |
|---|---|
| API contract | **frozen** — see [`docs/API.md`](docs/API.md) |
| Stub server | working, 27/27 smoke checks |
| VTpass client | written, dry-run verified, 30/30 tests — **live token unproven** |
| Vault contract | not started (M1) |
| Agent + LLM | not started (M2) |
| Voice (Whisper) | not started (M4) |
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
python3 smoke_test.py        # 27 checks, exits 1 on failure
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
Ikeja "Home meter", DStv Compact, MTN airtime, "4 days left") so screens render
with the numbers already in the design.

## Repo layout

```
backend/
  server.py        zero-dependency API stub
  smoke_test.py    27 checks, covers every endpoint and error code
  vtpass.py        VTpass client, dry-run by default
  test_vtpass.py   30 tests, including the CLI wiring
  fixtures/        captured + modeled VTpass responses (see its README)
docs/
  API.md           the frozen contract — read this first
```

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

`fixtures/service-variations_ikeja-electric.json` is a real captured response. Every
other fixture is **modeled on the documented shape and has never been seen live** —
replace them with real captures the moment you have credentials.

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
| M1 | Vault contract + caps on testnet | never cut |
| M2 | Agent server, signed `pay()` | never cut |
| M3 | Real token vending, receipts | never cut |
| M4 | Telegram + Whisper voice | 4th |
| M5 | NEAR Intents funding | 3rd |
| M6 | AC telemetry + suggestions | 1st |
| M7 | Frontend wired, demo recorded | — |
