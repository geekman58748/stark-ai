# Stark — handoff

**Written 2026-10-20, last resumed 2026-10-24 (reminders, computed suggestions, real
audio in, streamed voice).** If you are an agent picking this
up, read §0 and then §1–3 before touching anything. Sections 9–11 are the honest list of
what is broken, guessed, or still unproven. Nothing in this repo is production code — it
is a contract stub, a bill-API client, an agent that can sign but has never broadcast,
and an undeployed vault contract, built to unblock a frontend developer working in parallel.

---

## 0. Resume here — state as of 2026-10-24 (M2 + M3 + M4 built, reminders, real audio in)

### The intelligence layer, probed (2026-10-24)

Eleven real questions through `/v1/voice` against the live model
(`google/gemini-2.5-flash-lite`, chosen for speed). Right without help: balance, most
recent subscription, reference/meter digits, renewal date, units left, a typo'd
"subscripshun", and an honest refusal for WhatsApp/Telegram. One model call each, no
tool round trip: **1.1–1.5s**, with occasional 2.6–3.2s provider outliers.

**Two failures were serious and are fixed.** With `pay_bill` the only tool offered,
questions that merely mentioned money reached for it: "if I pay DStv and top up 5
thousand, how much is left?" **paid ₦5,000 of airtime**, and "I'm confused, DStv says I
owe, what should I do?" tried to pay DStv. Three defences now, and the first two are
code rather than prompt:

1. `_tools_for(has_snapshot, transcript)` offers **no tools at all** on a question —
   read questions (what/read/show/when/how…), hypotheticals (if/what if/how much
   would), advice (should I/confused/why/explain). Nothing to call, nothing to spend.
2. `asks_instead_of_paying()` is also checked inside `pay_bill`
   (`not_a_payment_request`), so a model that ignores every instruction still cannot
   charge on a question.
3. The prompt says a question is not an instruction, and that a hypothetical is
   arithmetic to answer, not a payment.

Permission and confirmation still pay: "can you pay my DStv" and a bare "yes" are not
questions under the rule. Verified after the fix: all five question shapes attempted
nothing (`actions: []`), the hypothetical returned the right subtraction (₦64,200 −
₦7,900 − ₦5,000 = ₦51,300), and "pay 5000 for electricity" still delivered with a
token. 295 unit tests, 70/70 smoke.

Also fixed in the same pass: the model invented "you paid your last DStv bill last
week" (no such payment existed). The prompt now forbids claiming a past payment that is
not in the last five, and the answer is honest: "the last payment recorded was for your
electricity bill". What it still cannot do is in the README: no sending or forwarding
anywhere, no new meter number, no bill it has not been given.

### Reminders, computed suggestions, real audio in (2026-10-24, latest)

Three things that were promised in copy are now code, and one lie was deleted.

| Check | Command | Result |
|---|---|---|
| Whole backend suite | `python3 -m unittest test_agent test_tg test_tts test_vending test_vtpass test_wake test_reminders test_suggestions test_live_paths` | **281/281 OK** |
| API smoke | `python3 smoke_test.py` (server running) | **70/70** |
| Frontend | `tsc --noEmit` (dashboard, `packages/api`), `biome check apps packages` | clean |

**Reminders (`reminders.py`).** A bill can carry `renews_on` (additive `Bill` field,
`PATCH /v1/bills/{id}` sets, `""` clears, nonsense is 400 `bad_renews_on`). Every bill
inside a **7-day window** appears in `state.due_soon` — including overdue inside that
window, which is the loudest reminder there is — and `/v1/suggestions` renders it as
`bill_due`. A background loop (`start_reminder_loop`, `STARK_REMINDER_TICK`, default
300s) pushes the same line to linked Telegram chats **only when a bot token exists**;
the claim is logged in memory so one renewal is never nudged twice in a run. Nothing
depends on the thread: the same facts are in `/v1/state` and the agent's snapshot.

**Suggestions are computed (`suggestions.py`).** The old hardcoded list is gone —
including `"Your AC is 78% of your usage"`, which no data ever supported. Each line
now needs the data behind it: meter runway from ≥2 delivered electricity top-ups on
different days (`units_low`), else from the state's own estimate (`units_low_estimate`,
worded as an estimate); ≥80% of the monthly cap (`cap_near`); ≥2 devices reporting
telemetry in 24h with one at ≥60% of average load (`load_imbalance`); renewals inside
the window (`bill_due`). **No data, no line** — an empty list is honest, so no check
asserts a minimum length. Capped at 4, worst first.

**M4 finished: real audio in.** `/v1/voice` accepts the clip itself — base64 `audio`
(+`audio_type`) or a multipart `audio` part, ≤8MB — and sends it to Whisper before the
wake gate and agent. The response carries `stt: ok|failed|no_key`; when nothing was
heard the transcript is `""`, the agent is never called and the reply says so. A
transcript is never invented. `transcript_hint` stays as a probe for tests only, and
the Talk screen now sends the recorded blob. Whisper's MIME naming is fixed: the clip
is filed as `audio.webm`/`audio.ogg`/`audio.wav` from what the browser actually
recorded, not `audio.wav` regardless (which mis-decoded a webm).

**Two bugs found on the way out, both measured.** (1) `GET /v1/speak/stream` fell
through to the JSON sender after streaming, so it wrote the audio, threw
`UnboundLocalError: payload`, and appended/500'd behind a valid clip — the smoke
check passed because it only looked at the first bytes. Fixed in the dispatcher, and
the smoke check now asserts no error body trails the audio. (2) The provider **refuses
WebM as a container** (HTTP 400 "audio could not be processed", any filename), which
is exactly what a Chrome `MediaRecorder` produces — so the browser path could never
transcribe as first written. `stt.hear` now decodes non-WAV/OGG clips to 16 kHz mono
WAV with `ffmpeg` before sending. Verified live 2026-10-24: the same spoken sentence
sent as WAV, OGG/Opus and WebM all return the right transcript. **`ffmpeg` is now a
requirement for voice input, not just Telegram**; without it a WebM comes back
`stt: failed`, never guessed.

**Still true, and unchanged by the above:** no Telegram bot token has ever been set
(so no reminder has been pushed, and the webhook still refuses every real update),
VTpass is still fixture-backed (§10.1), and none of this is deployed.

### M4 — Telegram door, audio pipeline, identity linking

`/v1/voice` is no longer the only way in. A Telegram bot now runs the same agent
behind the same policy gate, and the §8A identity design is real code:

```
Telegram update → webhook secret → dedupe → identity gate → wake gate (voice only)
                → Agent.respond → reply in the chat
```

| Check | Command | Result |
|---|---|---|
| Telegram adapter, identity, audio | `python3 -m unittest test_tg` | **16/16 OK** |
| Agent, policy, signing | `python3 -m unittest test_agent` | **59/59 OK** |
| Payment, store, vending | `python3 -m unittest test_vending` | **44/44 OK** |
| VTpass client | `python3 -m unittest test_vtpass` | **30/30 OK** |
| API smoke | `python3 smoke_test.py` (server running) | **50/50, all good** |

New files: `telegram.py` (the adapter), `identities.py` (link codes, identities,
dedupe — same Postgres database as the receipts), `audio.py` (ffmpeg → 16 kHz mono WAV),
`stt.py` (Whisper client), `test_tg.py`.

**It fails closed, on purpose.** With no secrets the webhook refuses every update:

| Env var | Without it |
|---|---|
| `TELEGRAM_BOT_TOKEN` | adapter is `disabled` — every update is `401 webhook_unconfigured` |
| `TELEGRAM_WEBHOOK_SECRET` | same — an unauthenticated webhook is a wallet anyone can talk to |
| `NEAR_AI_API_KEY` | voice notes get "I cannot hear voice notes right now — text is working", never a guessed transcript |
| `STARK_TG_OWNER_ID` | link codes bind to `user_tunde` (the single demo user) |

To go live: create a bot with BotFather, then
`TELEGRAM_BOT_TOKEN=... TELEGRAM_WEBHOOK_SECRET=$(openssl rand -hex 32)` and point
the webhook at `/v1/tg/webhook` with `secret_token` set to that same value.

**What the adapter enforces** (each has a test):

- **Verify before parsing.** The raw body is checked against the secret header in
  constant time before any JSON is read (§8A).
- **An unlinked chat never reaches the agent.** It gets link instructions and
  nothing else — no balance, no bills, no payment.
- **Link codes** are 6 digits, single-use, 10-minute TTL, stored hashed, with 5
  attempts per sender per 10 minutes.
- **Dedupe** on `message_id`: Telegram re-delivers updates, and a second delivery
  cannot pay twice.
- **The wake gate applies to voice, not typing.** A voice note must open with an
  attempt at the wake word — the same rule `/v1/voice` uses — because a note can be
  recorded by accident. The rule lives in **one place (`wake.py`)** and tolerates
  what recognizers do to "stark": reported transcripts of `start`, `stock`, `starn`
  and `stop` are treated as the address and rewritten to `Stark, …` before the
  agent sees them (2026-10-24 — before this, saying the wake word through an accent
  got you silence, which is worse than a false wake). The attempt has to open the
  utterance, possibly after filler (`hey`, `um`, `so`), so "I start the car" is not
  a wake word. Ordinary speech is still ignored. A typed message in a DM is
deliberate. One brain, one gate policy, two sensible UIs.

**What M4 is not:** no TTS yet (replies are text; the provider is still an open
decision), and the bot has never received a real update. Whisper itself is now
live-verified (2026-10-22): `stt.py` returned real transcripts from generated speech,
including "Hello Stark, what is my light bill?". `test_tg.py` stays hermetic: agent,
transport and transcription are injected.

### Talk screen is hands-free (2026-10-24)

The mic no longer needs a tap per question. One wake ("Hey Stark", or a near-miss
the server accepts) opens a session that **has no idle timeout** — after each answer
the recognizer restarts itself, so a follow-up needs no wake word, and a pause does
not end it. It sleeps only on an explicit dismissal ("go to sleep", "stop
listening", "that's all", "I'm done" — `isSleepIntent`, checked client-side before
any API call), a tap on the orb, a real microphone error, or the tab going hidden.
*2026-10-24, second pass:* the first version refreshed a 20-second window on every
exchange, which measured a long answer plus a moment's thought as "gone quiet" and
hung up a normal five-turn conversation.

What it deliberately does *not* do:

- **It does not listen while Stark is speaking** (the recognizer would hear the
  reply), and it does not listen while a request is in flight. Both resume when
  the clip ends or the words land.
- **The session is client-side.** Continuation turns are prefixed `Stark, …` by the
  Talk screen — the same thing typing and `?q=` do — so the server's wake gate is
  unchanged and still refuses anything raw. No session token, no new endpoint.
- `console.debug("[wake] ignored: …")` in DEV logs transcripts the gate refused:
  that log is the feed for `wake.py`'s alias set. Add to it only what was actually
  heard.

### Frontend contract breadth (2026-10-22)

### M3 — vending and persisted receipts (latest)

**What changed.** The payment path now buys instead of pretending to:

```
policy check → sign pay() → record the intent → VTpass buy → charge → speak the token
```

| Check | Command | Result |
|---|---|---|
| Payment, store, vending | `python3 -m unittest test_vending` | **44/44 OK** |
| Agent, policy, signing | `python3 -m unittest test_agent` | **59/59 OK** |
| VTpass client | `python3 -m unittest test_vtpass` | **30/30 OK** |
| API smoke | `python3 smoke_test.py` (server running) | **50/50, all good** |
| Persistence | pay → restart → `/v1/state` + `/v1/activity` | balance, spent and the receipt all survived |

New files: `receipts.py` (SQLite store), `vending.py` (bill → vendor), `catalog.py`
(VTpass products, plans and prices from captured fixtures), `payments.py` (the
two-phase service), `test_vending.py`. `server.py` no longer keeps balance or activity
in memory — both come from the store, so a restart cannot leave history and balance
disagreeing.

**The three decisions that matter**

1. **Record before buying.** The receipt is written with a `request_id` and status
   `pending` *before* the vendor call. If the process dies mid-purchase the id
   survives and the purchase is re-queried, not duplicated (`019`).
2. **Charge on delivery only.** `pending` and `failed` never move money, and a
   `delivered` result with no token is downgraded back to `pending` rather than
   charged.
3. **A retry reuses its `request_id`.** `find_pending(bill_id, amount)` is how the
   same intent settles an in-flight purchase instead of buying twice.

**Still true:** `STARK_VENDING` is `dry` by default and reads `fixtures/pay_ok.json`;
**no real purchase has ever been made** (§10.1). What *is* confirmed is the catalogue:
electricity, airtime, data and TV all resolve to real VTpass service ids and prices
captured from the sandbox into `fixtures/` (§10.16 covers the holes).

**Products, and how they are priced** (`catalog.py`, 2026-10-22 capture):

| Kind | Services | Priced by |
|---|---|---|
| electricity | `ikeja-electric` / `prepaid` | amount |
| airtime | `mtn`, `airtel`, `glo`, `etisalat` | amount, inside the vendor's min/max |
| data | `{mtn,airtel,glo,etisalat}-data` | **plan** (37/26/79/18 bundles) |
| tv | `dstv`, `gotv`, `startimes`, `showmax` | **plan** (67/7/25/11 bouquets) |

A plan is a fixed price, so a plan bill carries `plan` + `plan_price_ngn` and any
other amount is refused (agent and gateway both). **The per-payment cap moved from
₦5,000 to ₦10,000** because DStv Compact is ₦7,900 — a ₦5,000 cap made the TV bill
impossible to pay.

### Frontend contract breadth (2026-10-22, latest)

The design screens needed routes the frozen contract did not have. Nine were added,
all **additive** — no existing field, shape or status code changed:

| Screen | Routes |
|---|---|
| Limits | `GET /v1/limits`, `PATCH /v1/limits` |
| Add bill | `POST /v1/bills`, `GET /v1/plans` |
| Bill detail | `PATCH /v1/bills/{id}`, `DELETE /v1/bills/{id}` |
| Wallet / Fund | `GET /v1/wallet`, `POST /v1/wallet/topup`, `POST /v1/wallet/withdraw` |

These are real against the stub, not mocked handlers: adding or deleting a bill
re-scopes the agent's meter allowlist; `PATCH /v1/limits` replaces the agent's own
`Limits` object in the same process, so the next voice turn is refused at the new
cap; top-up and withdraw write ledger rows through the SQLite store. Plans come from
the captured VTpass catalogue, and the client never sends a price — `plan_price_ngn`
is resolved server-side.

`POST /v1/payments` now enforces the **per-payment** cap as well as the monthly one,
in the same order as the agent (§10.13). 50 smoke checks cover the new routes.

What is still in memory: bills, limits and `units_left`. A restart resets them while
receipts and the wallet survive (§9).

### M2 — the agent server

**M2, the agent server, is built and green.** `/v1/voice` no longer returns canned
regex strings: it runs a real tool-using loop with a hard policy gate in front of
every payment. The smoke suite has since grown to 50 checks (§0, frontend routes).

| Check | Command | Result |
|---|---|---|
| Agent, policy, signing | `python3 -m unittest test_agent` (in `backend/`) | **59/59 OK** |
| VTpass client | `python3 -m unittest test_vtpass` | **30/30 OK** |
| API smoke | `python3 smoke_test.py` (server running) | **50/50, all good** |
| Vault contract | `cargo test` (with `RUSTUP_HOME`, §1) | **38/38** (unchanged) |

New files in `backend/`: `agent.py` (tools, routing, model loop), `policy.py` (the
vault's rules in Python), `near_tx.py` (borsh + ed25519 + base58 + RPC),
`vault_signer.py` (function-call key wiring), plus M3's `receipts.py`,
`vending.py`, `payments.py`, `test_agent.py` (59 tests) and `test_vending.py`.

**What M2 actually does**

```
transcript → model picks a tool → policy gate → sign pay() → book the payment → reply
```

- The gate is enforced in code (`Agent._pay_bill`), not asked for in the prompt. A
  scripted model that demands ₦50,000 is refused; there is a test for exactly that.
- `policy.py` mirrors `contracts/vault/src/policy.rs`, and a test reads the Rust
  source and fails if a code or sentence drifts.
- Signing is stdlib only: hand-rolled borsh, RFC 8032 ed25519, base58. **Dry by
  default** — a signature is built, nothing is broadcast (`STARK_BROADCAST=1` sends).
- With no `NEAR_AI_API_KEY` the server uses a deterministic model that emits the
  same tool calls. The key stays a config value, so the tests are hermetic.

**What M2 does not do:** it does not call VTpass (that is M3), it does not broadcast
anything by default, and its two network-facing pieces have never run against a live
service — see §10.11 and §10.12.

---

The previous session ended mid-command: it was probing the Rust toolchain and its last
`rustup` call failed, so it never reported. Everything below was **re-run and observed**
by the resume session; nothing is inherited on faith.

| Check | Command | Result |
|---|---|---|
| VTpass unit tests | `python3 -m unittest test_vtpass` | **30/30 OK** |
| API smoke | `python3 smoke_test.py` (server running) | **50/50, all good** |
| Vault unit tests | `cargo test` (with `RUSTUP_HOME`, §1) | **38/38**, 0 failed |
| Vault lint | `cargo clippy --all-targets -- -D warnings` | **clean** |
| Vault wasm typecheck | `cargo check --target wasm32-unknown-unknown` | **clean** |
| Deployable artifact | `cargo build --target wasm32-unknown-unknown --release` | **`stark_vault.wasm`, 203 KB** |

The wasm row is new and it matters: **`cargo-near` is not needed to produce a deployable
artifact.** Plain `cargo` in release mode emits `stark_vault.wasm`; `cargo near` would only
add the ABI JSON and the `near deploy` convenience. §1 previously said "install cargo-near
before anyone says deploy" — that claim was too strong and is corrected there.

**Toolchain verdict: do not install Rust.** The toolchain is present at
`/Users/mac/.rustup/toolchains/stable-aarch64-apple-darwin` (cargo 1.97.1). The failed
`rustup default stable` in the previous session resolved `$HOME` to the redirected profile
directory, downloaded six components, hit a DNS error, and rolled back. That is the §1
trap biting again, not a broken install.

**Repo drift was found and fixed.** `/Users/mac/stark` is *not* a git repository; the git
repository is `/Users/mac/stark-ai` with the project under `stark/`. The M1 contract had
been built only in `/Users/mac/stark`, so **the pushed repo did not contain `contracts/`
at all** — the public repo was missing the single never-cut deliverable. The working tree
of `/Users/mac/stark-ai/stark/` has now been resynced (contract, `.gitignore`, README,
this file) and re-verified there: 38/38 Rust tests and 30/30 Python tests green *in the
repo copy*. It is **uncommitted and unpushed** — that needs the human (§13 item 4).

**What is actually blocked, in priority order.** All four need the human; none are code:

1. **VTpass sandbox credentials** — still the kill-switch (§10.1). No amount of local
   work substitutes for one real `DELIVERED` token.
2. ~~**NEAR AI API key**~~ — **supplied 2026-10-22.** A real chat turn (with a tool
   call) and real Whisper transcripts are verified (§10.12).
3. **A funded NEAR testnet account** — unblocks the M1 deploy. The wasm is built; the
   deploy still needs an account with storage deposit plus `near-cli`/`cargo-near`.
   Note `near` CLI is **not installed** (checked this session).
4. **Authorization to push** the vault commit — §13 item 4.

Everything else in the queue is code, and the next code item is **M2** (§8).

---

## 1. Environment traps (read this first)

These cost real time. Each one was hit and diagnosed once already.

| Trap | Detail |
|---|---|
| **`$HOME` is redirected** | The shell's `$HOME` is `/Users/mac/.freebuff-profiles/last`, **not** `/Users/mac`. Any `~/Desktop` or `~/...` path resolves to a near-empty shadow directory. **Use absolute `/Users/mac/...` paths.** This caused a whole session of "the file doesn't exist" conclusions that were wrong. |
| **The design source is not in this repo** | It lives at `/Users/mac/Desktop/export/` — 24 artboards, 5 conversation transcripts, 2 docs, 12 reference images. Also `/Users/mac/Desktop/stRKREADME.md`, byte-identical to `export/README.md`. |
| **`/Users/mac/stark-ai` is a different thing** | It is an old, unrelated single-file landing page for hellostark.xyz (blue/purple gradient, "Intelligence, deployed."). Same brand name, **not** this design. Do not use it as the visual reference. Leave it alone. |
| **Only Python 3.14.7 exists** | `/opt/homebrew/bin/python3.14`. FastAPI + pydantic fail dependency resolution on it (pip backtracks until it times out). This is why everything here is **stdlib-only**. If you need FastAPI later, install Python 3.13 first or budget an hour. |
| **Background server lifecycle** | `nohup ... &` inside a tool call gets killed when that call's shell is cleaned up. Run `python3 server.py` as a *managed* background process instead. |
| **`pgrep -f "python3 -u server.py"` gives a false negative** | The process's `argv[0]` is the full framework path, so the pattern doesn't match even while the server is serving. Use `lsof -tiTCP:8000 -sTCP:LISTEN` instead. |
| **rustup needs `RUSTUP_HOME` for the same reason** | `cargo` reports "no default toolchain" even though `/Users/mac/.rustup/toolchains/stable-aarch64-apple-darwin` exists. Always prefix Rust commands with `RUSTUP_HOME=/Users/mac/.rustup CARGO_HOME=/Users/mac/.cargo PATH=/Users/mac/.cargo/bin:$PATH`. |
| **Do not `rustup default stable`** | With the redirected `$HOME` it downloads six components into `/Users/mac/.freebuff-profiles/.../.rustup`, dies on a DNS error for `rust-docs`, and **rolls back** — it looks like a broken toolchain and is not. The toolchain is already installed; just set `RUSTUP_HOME`. |
| **Two copies of the project exist** | `/Users/mac/stark-ai` is the actual git repo, with the project under `stark/`, and it is now the **newest** copy. `/Users/mac/stark` is an unversioned copy that is **stale** — it is missing all of M2/M3. Edits made only there do **not** reach the public repo; that is how `contracts/` went missing from the push on 2026-10-20. Edit the repo copy only, and never rsync the stale copy over it (§12). |
| **crates.io 403s curl but not cargo** | `curl https://crates.io/...` returns 403 with curl's default UA. Send `-A "cargo"`. Cargo itself is unaffected. |
| **near-sdk 5 refuses a plain `cargo build`** | It `compile_error!`s unless it can prove this is not an on-chain build. The fix used here is target-specific deps: the wasm branch uses plain `near-sdk`, the non-wasm branch adds `features = ["unit-testing"]`. |
| **`#[near]` on a plain struct derives borsh only** | JSON returns compile fine in host tests (the wasm wrapper is `cfg`'d out there) and then fail `--target wasm32-unknown-unknown` with `no Serialize`. Derive `near_sdk::serde::{Serialize, Deserialize}` explicitly, with `#[serde(crate = "near_sdk::serde")]`. |
| **`wasm32-unknown-unknown` had to be added** | Installed now. The deployable `.wasm` comes from plain `cargo build --target wasm32-unknown-unknown --release` (203 KB, verified) — `cargo-near` is **not** required to build it and is **not installed**; it only adds the ABI JSON and the `near deploy` convenience. |
| **`DATABASE_URL` is not optional** | Since the auth/storage switch the backend refuses to start without a Neon Postgres pooler URL (`sslmode=require`); the schema creates itself on first boot. Copy `.env.example` → `.env` first. |
| **Neon Auth refuses a request with no `Origin`** | Sign-up/sign-in must send `Origin: http://localhost:5174` — a browser always sends one, and without it the provider answers 400. The session token comes back as `token`; the backend verifies it against `<auth-url>/.well-known/jwks.json`. |
| **`bun` was missing for `turbo build`** | `npm run build` fails with `Unable to find package manager binary` until bun exists: `npm i -g bun`. |

---

## 2. What Stark is

An AI agent that pays your everyday bills from a crypto balance, within limits you set,
by voice or chat. Nigerian prepaid electricity is the first live market and the demo;
airtime, data, TV, internet and water are in scope.

**Product story in one line:** you say *"hello Stark, what's my light bill"* and it answers
with real balance, units and days left; you say *"top it up with five thousand"* and a real
20-digit meter token comes back, capped by rules enforced onchain.

Constraints carried from the design work:

- Black + burnt orange (`#C2410C`; `#F08A4B` for accents on dark screens)
- Crimson Pro headings, Inter body
- **No sliders anywhere.** No crypto jargon in user-facing app copy. Naira only.
- 3-step setup, phone version of every screen
- 3 jargon leaks remain in the design source — see §10

---

## 3. Hackathon facts (verified live from `nearhackathon.com/HACKATHON.md`)

Re-read that file before submitting; it warns dates and rules may change.

| Fact | Value |
|---|---|
| Build window | `2026-11-01T00:00:00Z` → **`2026-11-14T23:59:00Z`** |
| Judging | starts 11-16, results by 11-18 |
| Submit | `POST https://nearhackathon.com/api/applications` (12000-byte body) |
| Repo | must be **public** by the deadline — live at `github.com/geekman58748/stark-ai`, branch `main`. Layout and drift risk in §12 |
| Demo | human must publish a public X post with video/screenshots |

**Tracks we picked** — use the ids, not the display names:

1. **`realworld`** (lead) — stablecoin rails for everyday payments
2. **`security`** — spending limits, policy engines, function call keys, TEE attestation.
   The vault + capped function-call key + TEE inference is a textbook fit, and probably
   less crowded than `agents`.
3. **`agents`** — partial: Stark spends but does not earn or negotiate.

Deliberately **not** claimed: `privacy` (a weak fourth claim dilutes the README).

**Submission gotchas that silently kill you:**

- **`website` is a spam trap.** Any non-empty value rejects the whole submission. Never send it.
- One submission per team, **immutable**. Reusing a project name or email returns `409`.
- Payout needs a **mainnet named account** (`team.near`). Must be created by the human.
- `size` must be exactly one of `1`, `2 - 4`, `4 - 6`, `6 - 8`, `8+`.
- `requestId` is a UUID generated once and **reused on retries**.
- **AI judges** (Claude Code, Codex) read the README. Write "do X – see Y" steps; no marketing.
- `403` means submissions aren't open — do not retry. `409` means already submitted.

---

## 4. What's built

The API is FastAPI (`apps/backend/requirements.txt`; `bun run setup` in
`apps/backend` makes the `.venv`), laid out one module per feature after
awesome-nest-boilerplate — see `apps/backend/README.md` § Layout. Swagger UI is at
`/docs`. The contract is Rust, which needs `RUSTUP_HOME` set (§1).

```
apps/backend/
  app/main.py                  create_app(): modules, error filter, CORS, Swagger
  app/app_module.py            composition root: every repository and service, wired once
  app/guards/auth_guard.py     Neon Auth session -> Account, else 401
  app/database/neon.py         Neon Postgres over HTTPS: connection pool, schema, queries
  app/modules/<feature>/       controller + service + dtos/ (+ repository where it stores)
  app/modules/agent/           tool schema + routing + policy gate + model loop; policy.py mirrors policy.rs
  app/modules/chain/           borsh, ed25519, base58, RPC, sign pay(); vault signer, dry-run by default
  app/modules/receipt/         Postgres store: receipts + wallet, per account, request_id keyed
  app/modules/payment/         contract checks -> record -> buy -> charge on delivery
  app/modules/vending/         VTpass client + CLI, catalogue, kind -> product (dry-run by default)
  tests/                       unit tests, support.py (TempAccount, ApiHarness), smoke_test.py
  fixtures/                    VTpass responses (see §10 on provenance)
apps/contracts/
  vault/                       NEAR contract: caps, allowlist, owner withdraw
  vault/src/policy.rs          pure rules, no near-sdk, 20 tests
  vault/src/lib.rs             contract wrapper, 18 env-based tests
docs/
  API.md           218 lines   THE CONTRACT — frozen, additive changes only
README.md                       product intro, run instructions, ground rules
docs/HANDOFF.md                this file
```

### Run it

```sh
cd apps/backend
bun run setup                     # once
bun dev                           # http://127.0.0.1:8000, Swagger at /docs
```

```sh
cd apps/backend
bun smoke                         # exits 1 on failure (server running, STARK_STUB_RESET=1)
bun run test                      # every unit test
.venv/bin/python -m app.modules.vending.vtpass variations   # dry-run, no keys needed
```

### Verify the whole thing in ~30 seconds

```sh
cd apps/backend
.venv/bin/python -m unittest tests.test_vtpass 2>&1 | tail -3
.venv/bin/python -m app.modules.vending.vtpass buy --meter 04512345678 --amount 5000 --phone 08031234567
curl -s http://127.0.0.1:8000/v1/state
```

Expected: `OK` for the tests, a `DELIVERED` token block from the CLI, and JSON state with
`balance_ngn: 64200`.

---

## 5. The API contract

Full detail in [`docs/API.md`](API.md). All 20 routes, plus the stub-only reset:

| Method | Path | Status | Notes |
|---|---|---|---|
| GET | `/` | 200 | route index |
| GET | `/health` | 200 | liveness |
| GET | `/v1/state` | 200 | the whole dashboard in one call |
| GET | `/v1/plans` | 200 | priced data/TV plans; `?kind=` `?provider=` |
| GET | `/v1/bills` | 200 | array of bills |
| POST | `/v1/bills` | **201** / 400 / 409 | add a bill; `plan_required`, `duplicate_bill` |
| GET | `/v1/bills/{id}` | 200 / 404 | `unknown_bill` |
| PATCH | `/v1/bills/{id}` | 200 / 400 / 404 | rename, or change a data/TV plan |
| DELETE | `/v1/bills/{id}` | 200 / 404 / 409 | `bill_in_flight` while a payment is pending |
| POST | `/v1/payments` | **201** / 404 / 409 / 400 | `over_per_payment_cap`, `over_cap`, `insufficient_balance` |
| GET | `/v1/activity` | 200 | newest first, max 20 |
| GET | `/v1/limits` | 200 | monthly + per-payment cap, spent, remaining |
| PATCH | `/v1/limits` | 200 / 400 | `bad_limits`; reaches the agent immediately |
| GET | `/v1/wallet` | 200 | balance, spent, cap, added this month |
| POST | `/v1/wallet/topup` | **201** / 200 replay | deposit ledger row; `request_id` dedupes |
| POST | `/v1/wallet/withdraw` | **201** / 409 | `insufficient_balance` |
| GET | `/v1/suggestions` | 200 | finished sentences, `severity` + `reason` |
| POST | `/v1/telemetry` | **202** | AC meter bridge, watts |
| POST | `/v1/voice` | 200 | the one voice entry point |
| POST | `/v1/tg/webhook` | 200 / 401 / 400 | **M4 built.** Telegram-only; secret header required before parsing |
| POST | `/v1/_stub/reset` | 200 | **stub-only**, not part of the product contract |

**Conventions:** money is **integer naira** (`*_ngn`) — never floats, never strings.
Times are ISO 8601 UTC with `Z`. Errors are `{code, message, detail}` and callers branch
on `code`, never on `message`. CORS is fully open locally (preflight verified, 204).
Cap checks run **per-payment → monthly → balance** on both the REST route and the
agent, so the two paths cannot disagree about which refusal a payment gets.

**Voice gate lives on the server.** `/v1/voice` returns `{ignored: true, reply: null}` when
the transcript lacks `"stark"`; the client must stay silent. `reply` is already speakable
text — feed it straight to TTS.

**Mock values deliberately mirror the artboards** so the frontend renders with the real
design's numbers: balance `₦64,200`, cap `₦30,000`, spent `₦23,000` (leaving `₦7,000`),
`11.4` units, `4` days, bills = Ikeja "Home" / "Living room TV" (DStv Compact) / MTN
"My line", tariff `₦209/kWh` (so `₦5,000` → `23.92` units), sample token
`4821 0937 5512 8846 3019`. `/v1/activity` is seeded with the artboards' six entries:
three delivered electricity top-ups (`₦5,000 + ₦10,000 + ₦8,000`), one `declined`
`₦15,000` over the per-payment limit, one `₦1,000` automatic airtime top-up, and the
`+₦20,000` bank transfer.

---

## 6. Verified external facts

Each of these was checked against the live service or primary docs, not assumed.

| Fact | Evidence |
|---|---|
| VTpass sandbox is live | `POST sandbox.vtpass.com/api/merchant-verify` → **401** `"Invalid Credentials."` |
| Ikeja prepaid exists | `GET /api/service-variations?serviceID=ikeja-electric` → **200**, `prepaid` + `postpaid`, fee `N0` |
| VTpass auth | sandbox uses **basic auth** (username/password); `api-key`/`public-key`/`secret-key` headers also supported |
| VTpass purchase payload | `serviceID`, `billersCode`, `variation_code`, `amount`, `phone`, `request_id` |
| VTpass response codes | `000` ok, `011` bad args, `012` no product, `016` bad meter, `018` low balance, `019` duplicate, `020` confirmed, `030` unreachable, `034` suspended, `083` system error, `099` processing |
| **NEAR AI runs Whisper in a TEE** | `GET cloud-api.near.ai/v1/models` → 200, `openai/whisper-large-v3`, `owned_by: nearai`; `POST /v1/audio/transcriptions` → 401 without key |
| NEAR AI model count | 59 models; `openai/gpt-5-nano` is `0.05`/`0.4` |
| Pricing unit | `input`/`output` = **USD per 1M tokens**, confirmed against OpenAI's own published `gpt-4.1-nano` ($0.10/$0.40) and `gpt-5-nano` ($0.05/$0.40) |
| Demo AI cost | ~`$0.000064`/turn on `gpt-5-nano`; **~$0.013 for 200 turns**. Whisper adds ~`$0.001`. The real cost is the *electricity* (~₦5,000 ≈ $3), ~150× the AI bill |
| **Picovoice free tier is dead** | Free AccessKeys stopped 2026-06-30; the SDK refuses to run without a key. Porcupine is now paid — do not plan on it |
| Design claims hold | Crimson Pro + Inter in 24/24 artboards, `#C2410C` + `#F08A4B` in 24/24, **zero real sliders** (only a CSS `input[type=range]` reset), glass footer present, Stark rename 24/24 |

---

## 7. Decisions and why

| Decision | Rationale | Reversible? |
|---|---|---|
| **Stdlib instead of FastAPI** | pip cannot resolve FastAPI on Python 3.14 (hangs/`ResolutionImpossible`) | Yes, on 3.13 |
| **Contract frozen at `/v1`** | Two people building in parallel; drift is the main risk. Additive only; renames mean `/v2` | Additive yes, renames no |
| **Integer naira everywhere** | Avoids float rounding in money paths | No |
| **Wake gate server-side, not in the browser** | One implementation for Telegram, PWA and any speaker | No |
| **VAD + `"stark"` prefix instead of a wake-word engine** | Porcupine is now paid; Whisper is already in the pipeline; matches natural kitchen speech ("hello stark what's my light bill" in one breath) | Yes → openWakeWord if chatter becomes a problem |
| **Pending ≠ success** | VTpass returns `099`/`pending`; claiming success would lie to the user and strand the token | No |
| **`request_id` reused on retry** | A fresh id books a second sale (`019`) | No |
| **Telegram first, PWA second, ESP32 last** | Telegram costs nothing and is the fallback; ESP32 is the highest-risk path in a 2-week build | Yes |
| **AC is the tracked load, not light bulbs** | 4 bulbs ≈ ₦45–55/evening vs AC ≈ ₦1,900. Warning about bulbs makes the agent look dumb | Yes |
| **Telegram first, then WhatsApp; Apple via SMS/provider** | One adapter pattern, cheapest path to a demo; there is no public iMessage bot API. See §8A | Yes |
| **Bills and limits are editable, not just seeded** | The design has Add-bill and Limits screens; seeded-only would leave both dead. Editing re-scopes the agent's allowlist and caps in-process | Yes — persisting is additive |
| **The client never sends a plan price** | A plan is fixed-price at the vendor. Taking the amount from the UI is a way to underpay it, so the server resolves `plan_price_ngn` from the catalogue | No |
| **`stark-ai/` left untouched** | Different, older artifact; not the visual reference | — |

---

## 8. Milestones

Current date at handoff: **2026-10-20**. Hackathon opens 2026-11-01, so there are ~11
days of runway the original plan did not assume.

| # | Window | Deliverable | Status |
|---|---|---|---|
| **M0** | now → Oct 27 | Contract frozen, VTpass sandbox confirmed, NEAR AI key, AC meter decision | **partly done** |
| M1 | Oct 27–31 | Vault contract: monthly cap, per-payment cap, meter allowlist, `pay()`, events, unit tests | **built** — 38/38 tests, clippy clean, 203 KB wasm builds. **Not deployed** — needs a funded testnet account (§0.3) |
| M2 | Nov 1–3 | Agent server: NEAR AI LLM + tools, signs `pay()` with a function-call key | **built 2026-10-22** — 59 tests, gate enforced in code, signature dry-run. LLM client and RPC path unproven (§10.11–12) |
| M3 | Nov 4–5 | Real vending wired in, receipt store (tx hash ↔ token) | **built 2026-10-22** — 44 tests, 4 product families, dry-run; live blocked by VTpass `028` provisioning (§10.1) |
| M4 | Nov 6–7 | Telegram bot + Whisper voice + TTS | **built 2026-10-22, finished 2026-10-24** — Telegram + identity linking + Whisper (now fed real audio from both doors) + TTS (ElevenLabs Flash, Kokoro sidecar fallback, streamed). Fail-closed until secrets; no bot token has ever been set |
| M5 | Nov 8 | NEAR Intents funding, one cross-chain deposit | not started |
| M6 | Nov 9–10 | AC telemetry + suggestion engine | not started |
| M7 | Nov 11 | Frontend wired to the live API, **record the token clip** | not started |
| Wrap | Nov 12–14 | README with "do X – see Y", demo video, submit | not started |

**Cut if behind (in this order):** M6 → M5 → M4 (fall back to text).
**Never cut:** the onchain cap (M1) and the real token clip (M3/M7).

### M0 scorecard

| Item | State |
|---|---|
| API contract frozen | ✅ `docs/API.md` |
| Stub server working | ✅ 50/50 |
| VTpass client written + dry-run verified | ✅ 30/30 |
| NEAR AI audio model confirmed | ✅ `openai/whisper-large-v3` in `/v1/models` |
| **VTpass live token vending** | ❌ **THE KILL-SWITCH.** Credentials and meter verify are live; `/pay` returns `028` until the sandbox account is provisioned |
| NEAR AI API key | ✅ supplied 2026-10-22 — live turn + transcript verified |
| AC: 13A plug or hardwired breaker? | ❌ physical inspection |

---

## 8A. Multi-channel plan — Telegram, WhatsApp, Apple Messages, and auth

**Status 2026-10-22: the Telegram half and the identity/auth design are now built**
(§0 M4). Still design-only: WhatsApp, Apple/iMessage, SMS and iOS. This section is
the reference so the next agent does not re-litigate the platforms.

### What each channel can actually do

Platform facts checked **2026-10-22**; re-check before building — Apple and Meta both
move these rules.

| Channel | Verdict | The real constraint |
|---|---|---|
| **Telegram** | **build first** | Bot API + webhook, free, no business approval. Voice notes are OGG/Opus. This is M4. |
| **WhatsApp** | **build second** | Official **WhatsApp Business Cloud API** (Meta). Free test number for development; production needs a Meta business account and a verified number. Webhook verification, a 24-hour service window, template messages outside it, and per-message pricing. |
| **Apple Messages (iMessage)** | **do not promise for the demo** | Apple has **no public iMessage bot API**. Three paths: **Apple Messages for Business** through an approved provider (business approval and lead time; Poke became the first third-party AI approved for it in 2026); a **third-party iMessage API provider** (Linq, Sendblue, LoopMessage, Blooio — commercial bridges, not first-party; check ToS, SOC 2, cost, and account-ban risk); or **SMS** via Twilio/Infobip, which lands in Messages as green bubbles. |
| **iPhone “Hello Stark”** | **not possible as a custom wake word** | iOS reserves OS-level wake phrases for Siri. Apple's WWDC 2026 direction makes **App Intents** the path for Siri to reach an app (SiriKit is deprecated). Use App Intents + Shortcuts + the Action Button; in-app push-to-talk only. True always-listening is the wall Android. |

**Recommendation:** Telegram (M4) → WhatsApp Cloud API → wall-phone PWA → iOS via
Siri intents → SMS fallback. Do not build a native iOS app or an iMessage bridge for
the hackathon.

### One brain, many doors

```
Telegram / WhatsApp / SMS / Apple Messages / iOS / wall phone
        ↓  adapter: verify, dedupe, download media, resolve identity
   /v1/voice → wake gate → agent → policy → payment
        ↓
   reply text, or TTS audio in that channel's format
```

The adapter contract is deliberately small:

```
InboundMessage:
  channel          telegram | whatsapp | sms | apple | ios | wall
  channel_user_id  Telegram numeric id / E.164 / provider handle
  message_id       idempotency key, unique per channel
  text             str | null
  media_id         str | null   (voice note; the adapter downloads it)
  received_at      ISO 8601 UTC
```

Rules:

- The adapter verifies the webhook signature **before parsing**, dedupes on
  `message_id`, downloads and normalises audio, resolves the identity, then calls the
  same `Agent.respond` path `h_voice` uses.
- The agent must not branch on `channel` except to format the reply. Money logic stays
  in one place; `/v1/voice` remains the single entry point. Adapters are transport, not
  a second brain.
- Voice: transcode OGG/Opus (Telegram/WhatsApp) and M4A (iOS) to **16 kHz mono WAV** for
  Whisper. Cap duration and size; delete temp files.
- Replies: OGG/Opus voice note for Telegram/WhatsApp, MP3/M4A for iOS, text for SMS
  (MMS voice is unreliable).

### Identity linking (the part that protects the wallet)

Same Postgres database as receipts (`identities.py`), one set of rows per account.

```
accounts(id, auth_user_id, email, name, created_at, seeded_at)
        -- one row per Neon Auth user, created on first sign-in
channel_identities(channel, channel_user_id, user_id, display_name,
                   linked_at, last_seen_at,
                   PRIMARY KEY (channel, channel_user_id))
link_codes(code_hash, user_id, created_at, expires_at, used_at)
link_attempts(channel, channel_user_id, attempts, window_start)
processed_messages(channel, message_id, processed_at,
                   PRIMARY KEY (channel, message_id))
```

Flow:

1. In the Stark app/PWA the user taps **Connect Telegram / WhatsApp / SMS**.
2. The server issues a random 6-digit code, TTL 10 minutes, single use, at most 5
   attempts. Store the hash, show the code once.
3. The user sends `link 482913` from that channel.
4. The adapter resolves the code, binds `(channel, channel_user_id)` to `user_id`, and
   replies “Linked. Ask me for your balance.”
5. `unlink` removes the identity; `whoami` shows the linked account.

Rules that are not optional:

- **An unknown sender never creates a wallet and never pays.** The reply is link
  instructions only.
- One identity maps to exactly one Stark user; one user may have many identities.
- Phone channels normalise to **E.164**; Telegram uses the numeric user id. Never key
  on a display name.
- Linking is the **only** way a channel can claim an account. A `user_id` in message text
  or a webhook body is never trusted.
- Rate-limit link attempts; invalidate the code on success or after N failures.

### Auth — app sessions built, other channels not

The app's side is done: every `/v1` route needs a Neon Auth bearer token (401
without), and the Telegram webhook checks its own secret. Do not expose other
webhooks publicly until their checks exist.

**1. Channel authenticity — verify before parsing:**

| Channel | Check |
|---|---|
| Telegram | `X-Telegram-Bot-Api-Secret-Token` equals the secret set with `setWebhook` |
| WhatsApp | `X-Hub-Signature-256` = HMAC-SHA256 of the **raw body** with the Meta app secret |
| Twilio SMS | `X-Twilio-Signature` |
| Apple Messages for Business | the provider's signed request/JWT (provider-specific) |

A failed check returns 401, logs the channel and source IP, and processes nothing.

**2. User identity — resolve before acting:** look up
`(channel, channel_user_id)` in `channel_identities`; scope every read and payment to
that `user_id`. A missing link is a refusal, not a default user.

**3. App auth:** `Authorization: Bearer <session token>` — built, not designed. The
frontend signs up/in at Neon Auth, stores the token, and every `/v1` route verifies it
against the provider's JWKS (401 otherwise). `GET /v1/speak/stream` also takes the
token as `?token=` for the `<audio>` element. One token resolves to one `accounts`
row, which owns the wallet and receipts.

Also:

- **Idempotency:** `processed_messages` makes a retried webhook harmless. A payment
  keeps its existing `request_id` rule; no second charge on replay.
- **Rate limits:** per identity and per IP; reject oversized or over-long audio before
  download.
- **Logging:** no full message bodies, tokens or meter numbers; redact phone numbers;
  record `channel` + `user_id` on every payment for audit.
- **Secrets:** env vars only — bot token, webhook secret, Meta app secret, Twilio auth
  token, provider keys. Never in the repo.
- **Fail closed:** bad signature, unknown sender, expired code or missing token all mean
  “no payment”.

### Effort and order

| Step | What | Blocked on |
|---|---|---|
| M4a | Telegram adapter + webhook auth + link/auth tables | BotFather token; this section |
| M4b | Whisper transcription + TTS reply | NEAR AI key; TTS choice |
| M4c | WhatsApp Cloud API adapter | Meta app + test number |
| M4d | Wall-phone PWA | HTTPS tunnel, spare Android |
| M4e | iOS App Intents / Shortcuts | Apple Developer account |
| M4f | SMS fallback | Twilio/Infobip account, sender ID |

Each channel is roughly **1–2 days of code** once auth and media are real. WhatsApp
business verification and Apple Messages for Business approval are **calendar time, not
code time**. M4 ships Telegram text first, then voice; do not let the multi-channel
refactor delay the one working demo.

### Wall-phone wiring (the always-listening demo)

- **Phone = ears; Bluetooth speaker = mouth.** Bluetooth speakers are effectively
  output-only (A2DP); the headset mic (HFP) is poor. Use the phone's own mic.
- Wired 3.5 mm AUX or USB-C is more reliable than Bluetooth for an always-on install —
  no pairing drops after reboot.
- PWA in a kiosk browser + Wake Lock; HTTPS via Caddy/Cloudflare Tunnel; auto-start on
  boot; battery optimisation off; Wi-Fi reconnect.
- Keep it powered and ventilated. A phone held at 100% 24/7 will swell its battery.
- Mute the mic while TTS plays, or the speaker will re-trigger “stark”.

### Do not claim (yet)

- “Message Stark on iMessage” — there is no public API; only an approved provider or a
  commercial bridge can do it.
- “Hello Stark works from anywhere on iPhone” — Siri is the trigger; a third-party app
  cannot own the wake phrase.
- “The whole conversation is private” — channel providers and TTS sit in the path. The
  TEE claim covers Whisper only, and even that tier is unconfirmed (§10.3).
- “WhatsApp is live” — until the business/number is verified and the webhook is signed.

### Open decisions

- **TTS provider** — not chosen. Pick one that returns OGG/Opus (Telegram/WhatsApp) and
  MP3/M4A (iOS), and check its data-retention terms before writing privacy copy.
- **iMessage path** — skip for the hackathon; evaluate Apple Messages for Business or a
  provider afterwards.
- **WhatsApp business entity and number** — the human must own these.
- **Apple Developer account** — needed before any App Intents work.
- **Where auth lives** — decided: sessions are issued and verified by Neon Auth
  (JWKS, no server-side session store), and `accounts` maps the provider's user id to
  this app's wallet and receipts.
- **Link-code UX** — show the code in the app, not in a URL that can leak.

---

## 9. What's NOT built

Do not assume any of this exists:

- **Vault deployment** — the contract is written, tested and compiles to a 203 KB wasm
  (§0), but has never been deployed: no testnet account, no testnet NEAR, and neither
  `near` nor `cargo-near` is installed on this machine.
- **Agent server, partly** — tool routing, the policy gate and `pay()` signing exist
  and are tested (M2), the payment path buys through VTpass (M3), and the real NEAR AI
  model + Whisper are live-verified (2026-10-22). Still not real: no transaction has
  ever been broadcast or landed onchain, no live VTpass purchase has run, and
  `/v1/voice` still accepts `transcript_hint` rather than audio.
- **Token custody** — the vault's `balance_ngn` is an internal ledger. No NEP-141
  USDC, no `ft_on_transfer`, no settlement to the treasury. Say so plainly; do not
  imply money moves onchain today.
- **Auth** — Neon Auth sessions on every `/v1` route (401 `unauthorized` without one);
  the Telegram webhook authenticates with its own secret. Still missing: the
  channel-signature scheme for WhatsApp/SMS in §8A.
- **Persistence, partly** — accounts, receipts, wallets and channel identities are in
  Neon Postgres and survive restarts, scoped per account (M3 + auth). Still in memory: telemetry readings, **bills added through `POST /v1/bills`,
  the limits set through `PATCH /v1/limits`, and `units_left`**. A delivered payment
  updates the bill's `last_amount_ngn` / `last_units` / `last_paid_at` and adds its
  units to `units_left`, but all four reset on restart (and on `_stub/reset`). So a
  restart can keep the spending while forgetting the meter that caused it. Making
  these durable is additive and does not change any shape. `days_left` remains the
  seeded estimate.
- **Water and internet** — no confirmed VTpass product. Asking for them fails with a
  plain message and charges nothing; there is no silent "recorded" fallback.
- **Wallet funding has no payment rail.** `POST /v1/wallet/topup` writes a `deposit`
  ledger row and moves the balance; no card, transfer or onchain deposit is involved,
  and no money is real. `withdraw` is the same in reverse. Do not show a "Fund" flow as
  if it took a payment until a processor is wired in.
- **Bill edits do not rewrite history.** Renaming a bill leaves old receipts with the
  `bill_label` captured at payment time; deleting a bill keeps its activity rows.
  That is intended, but a UI that joins on `bill_id` must handle a missing bill.
- **Intents funding** — nothing.
- **Telegram bot — built, never live.** The adapter, webhook auth, dedupe, linking
  and the wake gate exist and are tested (§0 M4), but no bot token or webhook
  secret has ever been set, so the server refuses every update in production
  until the human configures `TELEGRAM_BOT_TOKEN` + `TELEGRAM_WEBHOOK_SECRET`.
  No real Telegram update has ever been received or answered. WhatsApp, SMS and
  Apple are still design-only (§8A).
- **Telemetry → suggestions** — `/v1/telemetry` readings now feed `load_imbalance`,
  but the sensor only exists in demo data: no real meter has ever posted. The line
  needs two devices, which is why it is quiet in a fresh install.
- **Reminder pushes** — the loop, the de-dupe and the Telegram send are written and
  tested; **no push has ever left the machine** because no bot token is configured.
- **Frontend** — being built by a human teammate against `docs/API.md`.
- **Demo video, X post, submission** — none.

---

## 10. Uncovered and unverified (do not let these get laundered into facts)

1. **VTpass live token vending has never happened.** Everything is fixture-backed. The
   wire shape matches VTpass's published SDK, and as of M3 the whole path — store,
   idempotent retry, charge-on-delivery — runs end to end against fixtures, but no `pay`
   call has returned a real token. **This is still the single thing that can kill the
   project.**

   **2026-10-22 update — auth and verification are now live-verified.** The sandbox key
   pair authenticates (POSTs need `api-key` + `secret-key`; the static key alone is 401),
   `merchant-verify` for the documented test meter `1111111111111` returns
   `Customer_Name: TESTMETER1` and `WrongBillersCode: false`, and a wrong meter returns
   HTTP 200 / `code: "000"` with `WrongBillersCode: true` in `content` — which the client
   now refuses as `016`. `/pay` returns `028 PRODUCT IS NOT WHITELISTED ON YOUR ACCOUNT`
   for both `ikeja-electric` and `mtn`, so purchases are blocked by **account
   provisioning**, not code. Ask VTpass to enable the products on the sandbox account;
   then the only remaining step is the one real `DELIVERED` token.
2. **All five purchase-response fixtures are hand-written.** The 13 catalogue fixtures
   (`services_*.json`, `service-variations_*.json`) were captured live on 2026-10-22;
   `merchant-verify_ok.json` and the four `pay_*.json` files are modeled, because a
   purchase needs credentials. `Customer_Name`, `units`, `token` nesting are all guesses
   at VTpass's real shape. `fixtures/README.md` records this. Replace them with real
   captures the moment credentials exist.
3. **Whisper's privacy tier is unknown.** NEAR AI has three tiers — **Confidential TEE**
   (their own fleet), **3P Confidential TEE**, and **Incognito** (gateway in a TEE but the
   model runs *outside* a TEE). The `/v1/models` payload has no tier field. If whisper is
   Incognito, **"the whole voice path stays private" is false** and must not be said to
   `security` judges. Check the model catalog before writing the README.

   **2026-10-22:** the pricing page labels `Qwen/Qwen3.8-27B` **Private TEE** (NEAR's
   own fleet), so the chat path can carry that claim. Whisper reports
   `owned_by: nearai` but its tier is still not stated in the API payload — confirm it
   on the catalogue before claiming the voice path is private.
4. **NEAR AI minimum top-up / starter credits unknown.** Usage is fractions of a cent; a
   required deposit is the only way cost becomes a real question.
5. **AC wiring unknown.** A 1–1.5 HP split on a 13A socket takes a 16A smart plug (watch
   compressor inrush). Hardwired to a breaker needs a CT clamp instead. Decides the hardware.
6. **Three jargon leaks still in the design source** (contradicts the stated no-jargon rule):
   `Talk.dc.html:63` user-visible status says *"Checking your vault"*;
   `Main.dc.html:284` website FAQ says *"the vault still blocks…"*;
   `Fund.dc.html:64` shows `USDT/USDC/ETH/SOL/BTC` and a raw `0x7a3F…91cE` address.
7. **Reicon icon provenance is unverifiable.** 234 inline `<svg>` elements (157 of them
   carrying `stroke-width="1.5"`), but no library name, CDN or attribution anywhere in the
   artboards. The "~180 Reicon swaps" claim cannot be confirmed by inspection — inlined
   SVG carries no provenance.
8. **NEAR AI audio billing unit is undocumented.** Bounded from both directions (token math
   and OpenAI's $0.003–0.006/min), so "pennies" is safe; the exact figure is not published.
9. **`whisper-large-v3` accuracy on Nigerian-accented English is unmeasured** — reasonable
   inference from model size, not a measurement.
10. **One non-hermetic test.** `test_live_flag_accepted_after_subcommand` makes a real
    network call (tolerates failure, so it won't flake-fail).
11. **The borsh transaction encoding has never been round-tripped.** `near_tx.py`
    encodes `TransactionV0` + `Action::FunctionCall` from `near-primitives`, and the
    tests pin byte offsets, the U128-as-string argument and `tx_hash = sha256(tx)` —
    but no signed transaction has been accepted by an RPC. A layout error is silent
    until the first live send. **Verify with one tiny testnet `fun` call before
    trusting it for a payment.**
12. ~~**The NEAR AI model client has never run.**~~ **Live-verified 2026-10-22.** With
    a key, `NearAiModel` returned a real completion from `Qwen/Qwen3.8-27B` and a
    parsed tool call (`get_balance`). `stt.transcribe` returned real Whisper
    transcripts. `openai/gpt-5-nano` was `is_ready: false` and is Incognito, so the
    default is now the NEAR-hosted Private TEE model.

    **2026-10-24 — the model changed for speed.** `NEAR_AI_MODEL` in `.env` is now
    `google/gemini-2.5-flash-lite`, because the demo was too slow to wait for:

    | Model (same prompt, 4 samples) | Median turn |
    |---|---|
    | `Qwen/Qwen3.8-27B` (was default) | **7.1s** (range 6.0–9.3) |
    | `Qwen/Qwen3.6-35B-A3B-FP8` | 9.8s |
    | `google/gemini-2.5-flash-lite` | **1.35s** |

    Three supporting changes in `agent.py`, in order of how much they saved:

    1. **The system prompt carries a snapshot** — `get_state()` + `list_bills()` +
       the five most recent payments — and when it is present the **read tools are
       not offered** (`Agent._tools_for`): only `pay_bill` goes to the model, because
       a prompt cannot act. First the reads were merely unnecessary, then they kept
       being called anyway (`list_bills` half the time, then `recent_activity`),
       each one costing a round trip. A snapshot read that throws puts every tool
       back — a wrong number is worse than a slow one.
    2. **An empty final message is retried once with the tools removed** — gemini
       returns zero tokens when tools are offered and the answer is already in hand,
       which used to surface as `Sorry, I didn't catch that.` after a payment had
       already gone through.
    3. **The voice streams** (`GET /v1/speak/stream`, see API.md) instead of arriving
       as one finished `data:` URL.

    Measured end to end against the live API (2026-10-24):

    | | before (today) | now |
    |---|---|---|
    | text for a read question | 2.3–2.8s, was 7.1s median at model level | **1.1–1.6s** (median 1.35, `actions: []`) |
    | text for a payment | 4.3s (two model rounds) | ~2.5s |
    | voice, first byte | 1.9s (Kokoro), 1.3s (buffered ElevenLabs) | **0.53–0.82s** streamed |
    | **first sound after asking** | 9–10s | **~1.9s** (a payment ~3.0s) |

    **The privacy note above is now stale, and that is deliberate:** this is a demo
    speed call, not a TEE one. If a judge asks about the model tier, either say
    `gemini-2.5-flash-lite` plainly or flip `NEAR_AI_MODEL` back to `Qwen/Qwen3.8-27B`;
    one env var, restart the server.
13. **Limits do not survive a restart.** `PATCH /v1/limits` mutates the agent's live
    `Limits` object, so both paths enforce the new caps immediately — but the values live
    in memory. A restart, or `_stub/reset`, restores ₦30,000 / ₦10,000. (The per-payment
    cap *is* now enforced on `POST /v1/payments`; it is no longer a two-rule-set gap.)
14. **In dry-run, every purchase returns the same token.** `fixtures/pay_ok.json` carries
    `4821 0937 5512 8846 3019`, which is also receipt `rcpt_0003`'s token. Perfect for
    tests, misleading in a screenshot: do not present a dry-run token as a live one, and
    do not let two purchases side by side in the same demo both show it.
15. **A pending payment does not reserve the balance.** The cap and balance are checked
    before the vendor call; a purchase that comes back pending is charged later on
    settlement. Two payments racing on the same intent can both pass the check —
    `find_pending` narrows it, it does not lock. Fine for one wall phone; revisit before
    more than one user.
16. **Plan prices are a snapshot.** `fixtures/service-variations_*.json` was captured
    2026-10-22. VTpass changes bouquet prices; a stale fixture means the agent refuses a
    payment the vendor would now accept (or accepts one it wouldn't). Re-capture before
    the demo, and note that `dstv79` is ₦7,900 *as of the capture*.
17. **A plan change does not touch past receipts.** `PATCH /v1/bills/{id}` rewrites the
    bill's `plan` and `plan_price_ngn` for future payments; an earlier receipt keeps the
    amount it was actually charged. Do not recompute history from the current plan.
18. **Airtime/data/TV have never been bought, only resolved.** The catalogue proves the
    ids and prices exist; `pay` for those products still has no live response (§10.1).
19. **The seed leaves only ₦7,000 of the monthly cap.** With the artboards' ₦23,000
    spent, a ₦7,900 DStv payment is an `over_cap` refusal until the month rolls over.
    That matches the design ("DStv · Nov 3" is next month), but it means the earlier
    "pay DStv ₦7,900 end to end" demo needs a lower `spent_ngn` or a fresh month. The
    plan path itself is still covered by `test_vending.py`.
20. **The TTS sidecar has never spoken to a real Telegram chat.** Kokoro-82M is
    live-verified locally (2026-10-23): the Talk screen shows text first (`speak:
    false`) and plays the voice fetched from `POST /v1/speak` a beat later; warm
    synthesis runs ~0.5–1.5s (MPS, RTF ~0.1), ~3s if the GPU re-warmed from idle
    (the sidecar's keepalive ping exists to prevent that); the OGG/Opus encode for
    `sendVoice` is proven with ffmpeg; and `bun smoke` passes **60/60 with a
    voice up, 58/58 with voice off** — against a *live* model (Qwen when written,
    `google/gemini-2.5-flash-lite` since 2026-10-24), which is why two smoke
    assertions were rewritten to stop pinning deterministic phrasing. No note
    has reached a real chat, because the bot has no live token. Two honest gaps on
    top: **Kokoro has no Nigerian English voice** (default `af_heart` is US female;
    Chatterbox cloning is the accent path), and the sidecar venv needs spaCy's
    `en_core_web_sm` installed explicitly (`tts-requirements.txt`) — misaki's
    auto-download dies inside a uv venv.

    **2026-10-24 — ElevenLabs Flash is now the first voice, live-verified the same
    day.** `tts.py` asks ElevenLabs (`ELEVENLABS_API_KEY`, set in `.env`) for every
    reply, wraps its 24 kHz PCM into a WAV, and falls through to Kokoro on any
    refusal, so the chain is ElevenLabs → sidecar → text. Four new tests in
    `test_tts.py` pin that chain against local fakes.

    Measured against the real API with a free key: **1.0–1.1s** for a Stark-length
    reply on `eleven_flash_v2_5`, against **1.4–1.9s** for Kokoro — the accuracy is
    the real win, the speed is the bonus. Two facts the docs did not hand us:
    **library voices are HTTP 402 `paid_plan_required` on a free key** (Rachel's id
    is rejected; only the account's **premade** voices work — default is now
    `onwK4e9ZLuTAKqWW03F9`, Daniel, and `GET /v1/voices` lists what a key owns), and
    `output_format=pcm_24000` is inside the free tier while 44.1 kHz needs Pro. The
    free tier is 10,000 credits/month, non-commercial — fine for the demo, worth
    knowing before a launch claim.

---

## 11. Code-level gotchas

- **`/v1/_stub/reset` exists** so the smoke test is repeatable. It is marked stub-only.
  Remove it before any public demo, or at least never document it to judges.
- **`smoke_test.py` assumes the server is running** and calls reset first. If it fails with
  connection errors, start `server.py`.
- **argparse `SUPPRESS` defaults** in `vtpass.py` — deliberate, so `--live` and `--fixture`
  work on either side of a subcommand. Don't "simplify" them away.
- **Cap order** in `/v1/payments` and in the agent is per-payment → monthly → balance,
  so one route cannot refuse a payment for a different reason than the other. A ₦20,000
  payment against a ₦10,000 per-payment cap returns `over_per_payment_cap`, not
  `over_cap`, even when both are breached.
- **`_rebuild_limits()` is how state reaches the agent.** It replaces the frozen
  `Limits` and assigns `AGENT.limits`; bill add/delete and limit patches all go through
  it. Mutating `LIMITS` in place would leave the agent enforcing stale rules.
- **VTpass `pay` returns 201 from our stub but HTTP 200 from VTpass itself** — the stub
  normalises to 201 for payments only. Keep that mapping in mind when wiring M3.
- **`extract_token` checks four locations** (`content.transactions.token`,
  `content.transactions.purchased_code`, top-level `purchased_code`, top-level `token`)
  because the real nesting is unconfirmed.
- **The 401 body from VTpass is a bare JSON string** (`"Invalid Credentials."`), not an
  object. `_parse` handles it; don't assume `dict` from that endpoint.
- **`FakeModel` is a test double, not a language model.** It classifies with regexes
  and emits the same tool-call envelope a real model does. If you "improve" its
  phrasing you are changing what the demo says, not what the agent can do.
- **One agent per process.** `server.py` builds the agent once at import (`AGENT`), so
  each process has one toolbox over the module globals. `_stub/reset` restores those
  globals and the agent follows automatically — do not cache state inside the agent.
- **The agent signs before it books.** Deliberate: an unbroadcast signature costs
  nothing, an unauthorised purchase is a real problem. M3 kept that order: policy →
  sign → record → buy → charge.
- **Charge happens after delivery, inside `PaymentService._apply`.** Moving the charge
  earlier (or adding one on the pending path) turns a vendor hiccup into a customer who
  paid twice. There are tests for pending, failed, no-token and settlement races.
- **`receipts.api_shape()` is the contract surface.** `store.get()` returns the raw row
  (with `vendor_code`, `vendor_message`); only `api_shape` decides what the API shows.
- **`POST /v1/_stub/reset` replaces the signed-in account's rows in Neon Postgres.** It
  is for tests and demos only. Never call it against a database whose history matters.
- **Fail closed on signing.** If a signer is configured and cannot produce a signature,
  `_pay_bill` refuses the payment (`authorisation_failed`). Do not "retry without
  signing" to make a demo work.
- **`parse_amount` returns `None` when no amount was named**, and only then does the
  agent default to ₦5,000. Don't collapse the two — the distinction is what lets you
  tell "top it up" from "top it up with nothing".

---

## 12. Repo hygiene

**Where the repo actually is** (this section used to claim no git existed anywhere — wrong):

```
/Users/mac/stark-ai/            git repo, remote github.com/geekman58748/stark-ai, branch main
  apps/backend …                THE PROJECT since the monorepo move (2026-10-22): backend,
                                dashboard, website, contracts; docs/ sits at the root
  index.html                    the OLD unrelated landing page — leave it alone
  stark/                        the PRE-monorepo copy — stale, do not edit. A server
                                started from stark/backend once held :8000 and broke smoke
/Users/mac/stark/               STALE unversioned copy — missing all of M2/M3; do not use
```

Rules that keep this from drifting again:

- **Edit `/Users/mac/stark-ai/apps/…` and `/Users/mac/stark-ai/docs/…`** — the monorepo
  layout — and never `stark/` (pre-monorepo) or `/Users/mac/stark/` (unversioned, and
  *behind*: it lacks `agent.py`, `catalog.py`, `payments.py`, `receipts.py`,
  `vending.py`, `policy.py`, `near_tx.py`, `vault_signer.py`, both new test files and
  all 13 captured fixtures). **Never rsync either copy into the repo** — that would
  delete M2/M3 and the monorepo. If you need the unversioned copy refreshed, copy
  *from* the repo:
  ```sh
  rsync -a --exclude 'target/' --exclude '__pycache__/' /Users/mac/stark-ai/stark/ /Users/mac/stark/
  ```
- **The public repo is required by 2026-11-14.** The app auto-deploys to hellostark.xyz on
  push to `main`, so a push is a deploy — do not push broken code.
- `.gitignore` covers `__pycache__/`, `*.pyc`, `.venv/`, `.venv-tts/` (the Kokoro
  sidecar's venv), `.DS_Store`, `.env`, and now `target/` + `**/target/` (a near-sdk
  build is ~1 GB; `Cargo.lock` **is** committed).
- No secrets anywhere in the tree. VTpass credentials are read from env vars only.
- `index.html` (the old landing page) and `Desktop/export/` must not be modified — they are
  the human's artifacts and the design reference.

---

## 13. If you're the next agent, do this next

**In order. Items 1, 3 and 4 are external or human-gated. Items 2, 5 and 6 are done.
Item 7 is the next code.**

1. **VTpass: credentials supplied 2026-10-22; get the products whitelisted.** Auth and
   `merchant-verify` work (see §10.1). `/pay` is blocked by `028 PRODUCT IS NOT
   WHITELISTED ON YOUR ACCOUNT`, so ask VTpass to provision `ikeja-electric` and the
   other products on the sandbox account, then run:
   ```sh
   cd apps/backend
   set -a; . ./.env; set +a
   python3 vtpass.py verify --meter 1111111111111 --live
   python3 vtpass.py buy --meter 1111111111111 --amount 5000 --phone <their-phone> --live
   ```
   If it prints `DELIVERED` with a 20-digit token, **replace the remaining modeled
   purchase fixtures with real captures** and update `fixtures/README.md`.
2. ~~Write the vault contract (M1).~~ **Done 2026-10-20, re-verified 22:25:** `contracts/vault/`,
   **38 tests** (not 41 — that number was wrong here), clippy clean, 203 KB wasm builds with
   plain `cargo`. Still missing: **deploy to testnet**. It needs a funded account, then:
   ```sh
   RUSTUP_HOME=/Users/mac/.rustup cargo build --target wasm32-unknown-unknown --release
   # with near-cli installed and an account funded:
   near deploy <acct>.testnet stark_vault.wasm
   near call <acct>.testnet new '{
     "owner":"<acct>.testnet", "treasury":"<acct>.testnet",
     "monthly_cap_ngn":"30000", "per_payment_cap_ngn":"10000",
     "allowed_meters":["04512345678"]
   }' --accountId <acct>.testnet
   ```
   That argument list is copied from `pub fn new` in `src/lib.rs` (U128s go over the wire
   as strings). `per_payment_cap_ngn` must not exceed `monthly_cap_ngn` or `new` panics —
   which is itself one of the 38 tests.
3. ~~**Ask for the NEAR AI API key.**~~ **Done 2026-10-22.** Live chat + tool call and
   real Whisper transcripts verified. What remains: accept audio on `/v1/voice` (it
   still takes `transcript_hint`) and confirm Whisper's privacy tier before any TEE
   claim.
4. ~~`git init` and push a public repo.~~ **Done 2026-10-20:** `github.com/geekman58748/stark-ai`,
   branch `main`. **But the push predates M1**, so the remote has no `contracts/`. The repo
   working tree now has it (uncommitted, re-verified there) — **ask the human before
   committing and pushing**, because `main` auto-deploys to hellostark.xyz.
5. ~~**M2 — agent server.**~~ **Done 2026-10-22:** tool schema, routing, policy gate and
   `pay()` signing, 59 tests. Built against a fake model exactly as §0.2 said to, so the
   key is still missing without blocking anything. What is left from M2: **call the real
   NEAR AI model once** (§10.12) and **round-trip one signed transaction** (§10.11).
6. ~~**M3 — real vending + receipts.**~~ **Done 2026-10-22:** `vending.py`, `receipts.py`,
   `payments.py`, 44 tests. Record-before-buy, charge-on-delivery, retry-reuses-id all
   enforced. What is left from M3: **one live purchase with real credentials** (§10.1),
   then replace the modeled fixtures with real captures.
7. **M4 — Telegram bot + Whisper voice + TTS**, the next code item. Read §8A first:
   the adapter contract, identity linking and webhook-auth design are there, and the
   rule is “one brain, many doors”. ~~TTS~~ **Done 2026-10-23:** the Kokoro sidecar
   (`bun tts`, `apps/backend/tts_server.py`) speaks `/v1/voice` replies and Telegram
   voice-note replies, and every failure of that path falls back to text (§10.20).
   What remains of M4: real audio into `/v1/voice` (it still takes `transcript_hint`),
   a live bot token to prove one voice-note round trip, and whisper's privacy tier
   (§10.3) *before* any README claim — the wake gate already sits server-side
   (`h_voice`), so nothing there is waiting.

   **Identity linking is finished (2026-10-25).** The gap was that nothing except
   tests could mint a code, so every `/link` in a real chat was refused. Now
   `POST /v1/link/code` mints one (single-use, 10 minutes) with the bot's `t.me`
   deep link, `/start <code>` redeems it as well as `/link <code>`, and the
   dashboard's **Connect a chat** screen (`/connect`, linked from Settings) shows
   the digits and the one-tap link. The bot exists on BotFather as
   **@hellostarkai_bot** and the webhook is registered against
   `https://geddon.hellostark.xyz/v1/tg/webhook`. Still human-gated: the deployed
   `stark-api` needs `TELEGRAM_BOT_TOKEN` + `TELEGRAM_WEBHOOK_SECRET` in the
   Brimble dashboard, because secrets live there and not in `brimble.toml`.
   Until then the live webhook answers `401 webhook_unconfigured` and Telegram
   reports a delivery error — the code path itself is verified locally.
8. ~~**Auth + storage on Neon.**~~ **Done 2026-10-26:** the backend verifies Neon Auth
   sessions against the provider's JWKS (`auth.py`) and stores accounts, wallets,
   receipts and channel identities in Neon Postgres (`neon.py`, `receipts.py`,
   `identities.py`), scoped per account; the dashboard signs up and in at `/login`
   (`apps/dashboard/src/lib/auth.ts`) and `/v1` answers `401 unauthorized` without a
   bearer token. `stark.db` is dead — anything that read SQLite must use Postgres.
   Still human-gated: the deployed `stark-api` needs `DATABASE_URL` and
   `NEON_AUTH_BASE_URL` in its environment, same as the Telegram secrets above.

**Never without explicit human confirmation:** submit the application, publish on X, make
the repo public, sign transactions, spend tokens, deploy to mainnet, or commit secrets.

---

## 14. Appendix — reference values

**Design tokens:** `#0a0b0f`-family near-black, burnt orange `#C2410C`, accent `#F08A4B`
on dark, Crimson Pro (headings), Inter (body), helmet logo mark.

**Artboards (24)** in `Desktop/export/design-source/`: `Main` (website), `Connect`,
`AddMeter`, `Fund` (the 3 setup steps), `Dashboard`, `Bills`, `BillDetail`, `TopUp`,
`Activity`, `Wallet`, `Limits`, `Talk` (wall phone), `Telegram`, plus `m-*` phone versions
of all of them. Live canvas: `https://claude.ai/artifact/7EjFC1ozPTinbkhLHxZTEm`.

**Voice pipeline target:**
`audio → whisper-large-v3 (NEAR AI, TEE) → gpt-5-nano + tool schema → policy check →
sign pay() with function-call key → VTpass pay → token → TTS reply`.
Budget ~10s end to end; speak a filler ("checking your meter…") immediately.

**Hardware:** spare Android phone as the wall device (PWA, `getUserMedia`, Wake Lock API,
HTTPS mandatory — Caddy or a Cloudflare Tunnel), cheap Bluetooth speaker for output
(Bluetooth is output-only; the phone is the input device). ESP32-S3 is week-2 stretch only.
