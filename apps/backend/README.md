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
bun smoke                     # in another shell: 58 checks against the running server
```

With no configuration the server is fully offline: payments are dry-run against
captured fixtures, nothing is signed or broadcast, and a deterministic model stands in
for the LLM. Each variable in [`.env.example`](.env.example) switches one piece on.

| Command (from `apps/backend`) | What it does |
|---|---|
| `python3 server.py` | API on port 8000 (no `.env` loading) |
| `python3 smoke_test.py` | 70 end-to-end checks; the server must be running |
| `python3 -m unittest test_agent test_vending test_vtpass test_tg test_tts test_live_paths test_wake test_reminders test_suggestions` | 281 unit tests, hermetic, no server needed (`bun run test` from the root) |
| `bun tts` | the local Kokoro voice sidecar on :8010 (needs `.venv-tts`, see Voice output) |
| `curl -X POST http://127.0.0.1:8000/v1/_stub/reset` | back to the demo seed; deletes added bills |

`ffmpeg` on your `PATH` (`brew install ffmpeg`) is **required for voice input** —
Telegram's OGG and the browser's WebM are both decoded with it. Without it, voice
asks for text instead of guessing.

## Files

```
server.py        zero-dependency API stub, `/v1/voice` routed through the agent
smoke_test.py    70 checks, covers every endpoint and error code
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
test_vtpass.py   33 tests, including the CLI wiring and the live shapes
telegram.py      the Telegram door: webhook auth, identity, wake gate, then the agent
wake.py          the wake rule both doors share, tolerant of what recognizers do to "stark"
identities.py    channel identity linking and webhook dedupe, in stark.db
audio.py         voice note → 16 kHz WAV via ffmpeg, and WAV → OGG/Opus for replies
stt.py           speech to text on NEAR AI's Whisper, or an honest refusal
reminders.py     renews_on → due_soon window, the spoken reminder line, a de-duped push queue
suggestions.py   the suggestion feed, computed from meter, telemetry, receipts and renewals
tts.py           text to speech — ElevenLabs Flash when keyed (buffered, or streamed), else the local sidecar, else an honest silence
tts_server.py    the Kokoro-82M sidecar: OpenAI `/v1/audio/speech`, own venv
turnlog.py       opt-in conversation log: one JSON line per turn, clips beside it
test_turnlog.py  15 tests: the entry shapes, the files, and that a failing log never fails a turn
tts-requirements.txt  the sidecar's install list (separate venv, needs Python 3.12)
test_tg.py       22 tests: the Telegram door, its gates, the audio path and voice replies
test_wake.py     11 tests: the wake rule's typo tolerance, pinned to real mishearings
test_tts.py      35 tests: the TTS client, the sidecar's request handling, the Opus encode
reminders.py     the renewal window and the reminder sentences — pure, clock injected
test_reminders.py  20 tests: the window edges, overdue, sorting, one push per renewal
test_suggestions.py  24 tests: each line only when its data supports it, and never a fabricated one
test_live_paths.py  33 tests: the live HTTP paths (VTpass, NEAR AI, Whisper,
                 NEAR RPC) against real loopback servers, no credentials
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
python3 smoke_test.py        # 70 checks, exits 1 on failure
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
- **A question never spends.** Two rules in `agent.py` run before the model's choices
  matter: a turn that opens like a read question, or asks "if / what if / should I /
  why / explain" or sounds confused, is offered **no tools at all**; and `pay_bill`
  itself refuses such a transcript with `not_a_payment_request`. Both exist because of
  a measured failure on 2026-10-24: with `pay_bill` the only tool on the table,
  "if I pay DStv and top up 5 thousand, how much is left?" **paid the airtime**, and
  "I'm confused, DStv says I owe, what should I do?" tried to pay DStv. "Can you pay
  my DStv" still pays — that is permission — and a bare "yes" still confirms.
- **An unpriced charge asks instead of guessing.** Two more refusals sit in `_pay_bill`,
  both written after a live session on 2026-10-24 where "recharge my airtime number"
  bought ₦1,000 **twice, 29 seconds apart**, with the model choosing the figure both
  times. No amount spoken and no plan price → `amount_required` ("How much would you
  like to pay? Nothing has been charged yet."). The same bill, the same figure,
  delivered or pending within five minutes → `duplicate_payment`, unless the transcript
  says again / yes / confirm, so a refused repeat can still be confirmed. A plan-priced
  bill needs no figure — the plan is the figure — and seeded demo receipts (`seed-*`)
  are scenery, not a payment Stark just made.
- **It says what it cannot do.** The prompt forbids implying a message was sent. There
  is no forwarding to WhatsApp, Telegram, email or SMS: the model answers that plainly
  instead of inventing a receipt-sending feature.

```sh
python3 -m unittest test_agent     # 70 tests
python3 -m unittest test_vending   # 44 tests
python3 -m unittest test_vtpass    # 30 tests
python3 smoke_test.py              # 58 checks, server must be running
python3 -m unittest test_tg        # 22 tests: the Telegram door and its gates
python3 -m unittest test_tts       # 21 tests: the voice path, without torch
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

**Honest limits:** the borsh layout has never been round-tripped against a live RPC.
The NEAR AI model and Whisper *have* run live (2026-10-22). `/v1/voice` now takes real
audio — base64 `audio` in JSON or a multipart file part — and `transcript_hint` is kept
only as a probe for tests (2026-10-24). See [`HANDOFF.md`](../../docs/HANDOFF.md) §10.

## What it can answer

Everything in the snapshot: balance, monthly cap and what is left, each bill's label,
provider, **reference (meter/smartcard/phone number)**, plan and price, renewal date,
and the last five payments. So "what's my most recent subscription?", "read my meter
number", "when does my DStv renew?" and "how many units are left?" are one model call
each, no tool round trip (measured 1.1–1.5s, 2026-10-24). A hypothetical ("if I pay A
and top up B, what is left?") is arithmetic on those numbers, answered without paying.

It cannot: send or forward anything (WhatsApp, Telegram, email, SMS), issue a new
meter number or token, or see a bill that was never saved.

## Voice input (Whisper)

`/v1/voice` takes the clip itself — there is no "stub transcription" in the product
path any more (2026-10-24):

```sh
# the browser: a recorded Blob, base64'd. `audio_type` must be what was recorded.
curl -s -X POST http://127.0.0.1:8000/v1/voice \
  -H 'Content-Type: application/json' \
  -d "{\"audio\": \"$(base64 -i clip.webm)\", \"audio_type\": \"audio/webm\"}"

# anything that streams a file: multipart, the same field name
curl -s -X POST http://127.0.0.1:8000/v1/voice \
  -F audio=@clip.ogg \
  -F audio_type=audio/ogg
```

`transcript_hint` still exists and is only a probe for tests and `curl` — audio is
checked **first**, so a client that can record never has to fake words.

**WebM does not work at the provider, and that is measured, not assumed**
(2026-10-24). Whisper reads WAV and OGG/Opus; a Chrome `MediaRecorder` WebM comes
back HTTP 400 *"Audio could not be processed"* whatever filename or content type it
is given — the container itself is refused. So `stt.hear` decodes anything that is
not WAV/OGG to 16 kHz mono WAV with `ffmpeg` before sending (`audio.transcode`, the
same step a Telegram OGG already took), and names the result `audio.wav`. WAV and
OGG skip ffmpeg entirely. Without ffmpeg the clip is sent unchanged and the answer is
`stt: failed` — never a guessed transcript. That makes `ffmpeg` **required** for the
dashboard's voice button, not just for Telegram.

Every audio answer carries `stt`: `ok` (transcribed, then the wake gate and agent
ran), `failed` (nothing heard — `transcript: ""`, reply asks again) or `no_key` (no
`NEAR_AI_API_KEY` — reply says so, and the keyboard is the answer). **An unheard clip
never reaches the agent and never gets a made-up transcript.** Bad base64 is 400
`bad_audio`; over 8MB is 413 `audio_too_large`.

## Voice output (TTS)

Replies come back **spoken** when the local voice sidecar is up, and as text when it
is not — never slower, never blocked on it. `/v1/voice` carries an additive `audio`
field (a WAV data URL, or `null`); a Telegram voice note gets a voice note back
(OGG/Opus via `sendVoice`); the dashboard's Talk screen plays it.

**Amounts are spoken as words, not symbols.** Neither voice reads `₦`: ElevenLabs
and Kokoro both said the letter *N* ("Your balance is N sixty-four thousand…"),
measured 2026-10-24 by synthesising a real reply and transcribing the clip back. So
`tts.speakable()` rewrites `₦64,200` → `64,200 naira` before anything is synthesised —
WAV, stream and Telegram voice note all go through it. The reply the user *reads* keeps
the sign; only the voice is spelled to. A symbol in the middle of a sentence is the
only thing this touches: numbers, decimals and commas without `₦` are left alone
(`SpeakableCase` in `test_tts.py` pins both halves).

**Text never waits for voice.** The dashboard sends `{"speak": false}` so the words
land in one model turn, then fetches the voice from `POST /v1/speak` and plays it a
beat later. The sidecar keeps its GPU warm with a background ping
(`STARK_TTS_KEEPALIVE`, default 45s, `0` disables) because Metal re-warms kernels
after a quiet few seconds — without it the first reply of the minute paid ~3s.

**Two voices, ElevenLabs first.** With `ELEVENLABS_API_KEY` set, `tts.py` asks ElevenLabs
Flash v2.5 for the reply: a Stark-length answer comes back in well under a second
against ~2s for the local voice, and it reads `₦5,000`, "Ikeja" and dates correctly.
The raw 24 kHz PCM it returns is wrapped into a WAV inside `tts.py`, so nothing
downstream moves — the dashboard's `data:` URL, `ffmpeg` for Telegram and `/v1/speak`
all still see a WAV.

What the free tier actually buys: **10,000 credits a month** at 0.5–1 credit per
character on Flash — call it 10k–20k characters, ~13–26 minutes of speech, **70–130
Stark replies**. It is non-commercial, and **the Voice Library is not available to free
keys over the API**: asking for Rachel (`21m00Tcm4TlvDq8ikWAM`) returns HTTP 402
`paid_plan_required`, measured 2026-10-24. So a free key is limited to the account's
**premade** voices (`ELEVENLABS_VOICE_ID`, default Daniel — Steady Broadcaster; `GET
/v1/voices` lists them) and there is no Nigerian accent among them. A cloned or
library voice needs Starter ($6/mo, $1 for the first month), which is also where the
commercial license lives.

The chain never breaks: ElevenLabs down → the Kokoro sidecar → the text already on
screen. A key is optional forever, and the demo works without it.

The voice is [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) (Apache 2.0,
82M params), served by `tts_server.py` behind the OpenAI speech shape — the mirror
image of `stt.py`. It needs its own interpreter, because torch has no business in a
standard-library API:

```sh
# once, from the repo root
uv venv --python 3.12 .venv-tts
uv pip install --python .venv-tts/bin/python -r apps/backend/tts-requirements.txt

# every time (or: bun tts from the root)
cd apps/backend && ../../.venv-tts/bin/python tts_server.py
```

Then set `STARK_TTS_URL=http://127.0.0.1:8010` in `.env` (see `.env.example`).
Measured 2026-10-23 on an M1 Pro: ~2s for a typical reply on MPS and on CPU
(RTF ~0.25–0.3, so speech arrives faster than it plays on both). `STARK_TTS_VOICE`
picks the voice — `af_heart` (US female, default), `bf_emma` (UK female),
`am_michael` (US male). **Kokoro has no Nigerian English voice**; if the accent
matters, voice cloning (Chatterbox, MIT) is the path.

**Text is normalised before synthesis** (`normalize_for_speech` in `tts_server.py`):
`₦30,000` becomes "naira 30,000" (misaki read the glued ₦ as *three-zero-zero-zero-zero*),
em dashes become pauses (the voice said "dash"), brackets and slashes drop out, and
amounts the model spelled out as words ("five nine two zero zero") collapse back to
numerals. Meter tokens stay digit-by-digit. The agent's system prompt was rewritten
to match: figures for money, single spaced digits for tokens, commas not dashes.

**Streaming.** `POST /v1/speak` hands over a whole clip, which cannot start playing
until synthesis finishes (~1.3s). `GET /v1/speak/stream?text=…` sends the MP3 as
ElevenLabs produces it, and the Talk screen plays that first: measured **first byte
0.53–0.82s** against **1.25–1.30s** buffered, so speech starts while the clip is still
being built. The stream falls back to `POST /v1/speak` in the browser, and on the
server to a whole Kokoro WAV; no voice anywhere is a 503 `no_voice`, not silence.

Fails closed, exactly like `stt.py`: no key and no URL, both providers down, no
ffmpeg, or a Telegram refusal — the answer still arrives, just not spoken. `bun smoke`
proves both worlds: 58 checks with voice off (`audio` null), 60 with a voice up.

## Conversation log (turnlog)

To judge Stark on a real conversation rather than on a test, turn the log on
and every exchange appends one JSON line:

```sh
STARK_TURN_LOG=1 bun dev:backend     # or add it to .env; a path works too
tail -f apps/backend/logs/turns/turns.jsonl
```

A `kind: "turn"` line holds the whole exchange: `heard` (the transcript
verbatim), `said` (after the wake gate), `reply`, `actions` (what it actually
did), `code` (the rule that refused, when one did), `model`, and `ms` per
stage — `total`, `stt`, `agent`, `tts`. A **missing** stage key means that
stage did not run, not that it was instant. `outcome` is `answered`, `asleep`
(the wake gate kept it) or `unheard` (STT failed — no transcript, no agent,
no guess). When a clip was uploaded, `audio` points at `audio/<stamp>-in.webm`
sitting beside the log, so the words and the sound that produced them stay
together.

A `kind: "speak"` line is the other half of the exchange: `text` as written,
`spoken` as the provider received it (after the naira rewrite), the provider,
and `ms` — time to first byte on the stream, whole-synthesis time on
`POST /v1/speak`.

Off by default, `logs/` is gitignored, and a log that cannot be written is
discarded rather than returned as a 500.

## Bill API (VTpass)

Dry-run by default, so it works with no credentials:

```sh
python3 vtpass.py variations                       # prepaid | postpaid
python3 vtpass.py verify --meter 04512345678
python3 vtpass.py buy --meter 04512345678 --amount 5000 --phone 08031234567
python3 vtpass.py buy ... --fixture pay_pending.json    # exercise the pending path
python3 -m unittest test_vtpass -v                 # 33 tests
```

Two behaviours the agent depends on:

- **A token only counts when `code == "000"` and `status == "delivered"`.** A `099`/`pending`
  transaction must not be reported as paid — requery it with the same `request_id`.
- **Retries reuse the same `request_id`.** A new id on a retry books a second sale (`019`).

Add `--live` to hit the real API. It needs `VTPASS_ENV`, `VTPASS_USERNAME`,
`VTPASS_PASSWORD` (sandbox default), or the `VTPASS_API_KEY` /
`VTPASS_PUBLIC_KEY` / `VTPASS_SECRET_KEY` trio. Never commit them.

The 13 catalogue fixtures (`services_*.json`, `service-variations_*.json`) are real
captured responses (2026-10-22). The first authenticated calls captured
`merchant-verify_ok.json`, `merchant-verify_wrong.json` and
`pay_not_whitelisted.json` (code 028). The four remaining purchase fixtures
(`pay_ok`, `pay_pending`, `pay_low_balance`, `pay_duplicate`) are **modeled on the
documented shape and have never been seen live** — the sandbox account is not yet
provisioned for `/pay`. See [`fixtures/README.md`](fixtures/README.md).

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
