# Stark — handoff

**Written 2026-10-20.** If you are an agent picking this up, read sections 1–3 before
touching anything. Sections 9–11 are the honest list of what is broken, guessed, or
still unproven. Nothing in this repo is production code — it is a contract stub plus a
bill-API client, built to unblock a frontend developer working in parallel.

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
| Repo | must be **public** by the deadline — **this repo has no git at all yet** (§12) |
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

Everything is zero-dependency Python 3.14 stdlib. No venv, no install step.

```
backend/
  server.py        442 lines   API contract stub, mock data, in-memory state
  smoke_test.py    138 lines   27 checks: every endpoint + every error code
  vtpass.py        445 lines   VTpass client + CLI, dry-run by default
  test_vtpass.py   247 lines   30 tests incl. CLI wiring
  fixtures/                    VTpass responses (see §10 on provenance)
docs/
  API.md           218 lines   THE CONTRACT — frozen, additive changes only
README.md          121 lines   product intro, run instructions, ground rules
HANDOFF.md                     this file
```

### Run it

```sh
cd /Users/mac/stark/backend
python3 server.py                 # http://127.0.0.1:8000  (port 8000)
```

```sh
cd /Users/mac/stark/backend
python3 smoke_test.py             # 27/27, exits 1 on failure
python3 -m unittest test_vtpass   # 30/30
python3 vtpass.py variations      # dry-run, no keys needed
```

### Verify the whole thing in ~30 seconds

```sh
cd /Users/mac/stark/backend
python3 -m unittest test_vtpass 2>&1 | tail -3
python3 vtpass.py buy --meter 04512345678 --amount 5000 --phone 08031234567
curl -s http://127.0.0.1:8000/v1/state
```

Expected: `OK` for the tests, a `DELIVERED` token block from the CLI, and JSON state with
`balance_ngn: 64200`.

---

## 5. The API contract

Full detail in [`docs/API.md`](docs/API.md). Summary of the 12 routes:

| Method | Path | Status | Notes |
|---|---|---|---|
| GET | `/` | 200 | route index |
| GET | `/health` | 200 | liveness |
| GET | `/v1/state` | 200 | the whole dashboard in one call |
| GET | `/v1/bills` | 200 | array of bills |
| GET | `/v1/bills/{id}` | 200 / 404 | `unknown_bill` |
| POST | `/v1/payments` | **201** / 404 / 409 / 400 | `over_cap`, `insufficient_balance` |
| GET | `/v1/activity` | 200 | newest first, max 20 |
| GET | `/v1/suggestions` | 200 | finished sentences, `severity` + `reason` |
| POST | `/v1/telemetry` | **202** | AC meter bridge, watts |
| POST | `/v1/voice` | 200 | the one voice entry point |
| POST | `/v1/tg/webhook` | 200 | stub until the bot is built |
| POST | `/v1/_stub/reset` | 200 | **stub-only**, not part of the product contract |

**Conventions:** money is **integer naira** (`*_ngn`) — never floats, never strings.
Times are ISO 8601 UTC with `Z`. Errors are `{code, message, detail}` and callers branch
on `code`, never on `message`. CORS is fully open locally (preflight verified, 204).

**Voice gate lives on the server.** `/v1/voice` returns `{ignored: true, reply: null}` when
the transcript lacks `"stark"`; the client must stay silent. `reply` is already speakable
text — feed it straight to TTS.

**Mock values deliberately mirror the artboards** so the frontend renders with the real
design's numbers: balance `₦64,200`, cap `₦30,000`, spent `₦12,400`, `11.4` units,
`4` days, bills = Ikeja "Home meter" / DStv Compact / MTN airtime, tariff `₦209/kWh`
(so `₦5,000` → `23.92` units), sample token `4821 0937 5512 8846 3019`.

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
| **`stark-ai/` left untouched** | Different, older artifact; not the visual reference | — |

---

## 8. Milestones

Current date at handoff: **2026-10-20**. Hackathon opens 2026-11-01, so there are ~11
days of runway the original plan did not assume.

| # | Window | Deliverable | Status |
|---|---|---|---|
| **M0** | now → Oct 27 | Contract frozen, VTpass sandbox confirmed, NEAR AI key, AC meter decision | **partly done** |
| M1 | Oct 27–31 | Vault contract: monthly cap, per-payment cap, meter allowlist, `pay()`, events, unit tests, testnet | **not started** |
| M2 | Nov 1–3 | Agent server: NEAR AI LLM + tools, signs `pay()` with a function-call key | not started |
| M3 | Nov 4–5 | Real vending wired in, receipt store (tx hash ↔ token) | not started |
| M4 | Nov 6–7 | Telegram bot + Whisper voice + TTS | not started |
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
| Stub server working | ✅ 27/27 |
| VTpass client written + dry-run verified | ✅ 30/30 |
| NEAR AI audio model confirmed | ✅ `openai/whisper-large-v3` in `/v1/models` |
| **VTpass live token vending** | ❌ **THE KILL-SWITCH.** Needs sandbox credentials |
| NEAR AI API key | ❌ needs the human |
| AC: 13A plug or hardwired breaker? | ❌ physical inspection |

---

## 9. What's NOT built

Do not assume any of this exists:

- **Vault contract** — no Rust, no `near-sdk`, no testnet deployment.
- **Agent server** — no LLM call, no tool routing, no `pay()` signing. `/v1/voice` is
  regex-and-canned-string; `transcript_hint` is a stand-in for Whisper.
- **Auth** — none. The contract says a `Authorization: Bearer` header will appear in M4.
- **Persistence** — in-memory only; state resets on restart (`_stub/reset` restores seeds).
- **Intents funding** — nothing.
- **Telegram bot** — webhook returns `{ok: true, stub: true}`.
- **Telemetry → suggestions** — `/v1/telemetry` stores readings but nothing reads them.
  `/v1/suggestions` returns fixed copy.
- **Frontend** — being built by a human teammate against `docs/API.md`.
- **Demo video, X post, submission** — none.

---

## 10. Uncovered and unverified (do not let these get laundered into facts)

1. **VTpass live token vending has never happened.** Everything is fixture-backed. The
   wire shape matches VTpass's published SDK, but no `pay` call has returned a real token.
   **This is the single thing that can kill the project.**
2. **Five of six fixtures are hand-written.** Only
   `fixtures/service-variations_ikeja-electric.json` is captured live. `Customer_Name`,
   `units`, `token` nesting are all guesses at VTpass's real shape. `fixtures/README.md`
   records this. Replace them with real captures the moment credentials exist.
3. **Whisper's privacy tier is unknown.** NEAR AI has three tiers — **Confidential TEE**
   (their own fleet), **3P Confidential TEE**, and **Incognito** (gateway in a TEE but the
   model runs *outside* a TEE). The `/v1/models` payload has no tier field. If whisper is
   Incognito, **"the whole voice path stays private" is false** and must not be said to
   `security` judges. Check the model catalog before writing the README.
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

---

## 11. Code-level gotchas

- **`/v1/_stub/reset` exists** so the smoke test is repeatable. It is marked stub-only.
  Remove it before any public demo, or at least never document it to judges.
- **`smoke_test.py` assumes the server is running** and calls reset first. If it fails with
  connection errors, start `server.py`.
- **argparse `SUPPRESS` defaults** in `vtpass.py` — deliberate, so `--live` and `--fixture`
  work on either side of a subcommand. Don't "simplify" them away.
- **Cap is checked before balance** in `/v1/payments`, so an amount breaching both returns
  `over_cap`, not `insufficient_balance`. Mirrors the intended onchain ordering.
- **VTpass `pay` returns 201 from our stub but HTTP 200 from VTpass itself** — the stub
  normalises to 201 for payments only. Keep that mapping in mind when wiring M3.
- **`extract_token` checks four locations** (`content.transactions.token`,
  `content.transactions.purchased_code`, top-level `purchased_code`, top-level `token`)
  because the real nesting is unconfirmed.
- **The 401 body from VTpass is a bare JSON string** (`"Invalid Credentials."`), not an
  object. `_parse` handles it; don't assume `dict` from that endpoint.

---

## 12. Repo hygiene — outstanding

- **There is no git repository in `/Users/mac/stark`.** It has never been initialised, and
  the hackathon requires a **public repo by 2026-11-14**. Do this early; it's a hard
  requirement and trivially forgotten.
- `.gitignore` already covers `__pycache__/`, `*.pyc`, `.venv/`, `.DS_Store`, `.env`.
- No secrets anywhere in the tree. VTpass credentials are read from env vars only.
- `stark-ai/` and `Desktop/export/` must not be modified — they are the human's artifacts
  and the design reference. Both were verified untouched (git status clean / no mtimes
  after the session started).

---

## 13. If you're the next agent, do this next

**In order. Do not reorder into the vault without reading item 1.**

1. **Ask the human for VTpass sandbox credentials**, then run:
   ```sh
   cd backend
   export VTPASS_ENV=sandbox VTPASS_USERNAME=... VTPASS_PASSWORD=...
   python3 vtpass.py verify --meter <real-meter> --live
   python3 vtpass.py buy --meter <real-meter> --amount 5000 --phone <their-phone> --live
   ```
   If it prints `DELIVERED` with a 20-digit token, **replace the modeled fixtures with real
   captures** and update `fixtures/README.md`. If it fails, the project needs rethinking —
   find that out now, not on Nov 12.
2. **Write the vault contract (M1).** Rust + `near-sdk`. It depends on nothing external and
   can never be cut. Unit tests must prove an over-cap `pay()` fails and a valid one emits
   an event.
3. **Ask for the NEAR AI API key**, then replace `transcript_hint` with a real
   `/v1/audio/transcriptions` call. Check whisper's privacy tier *before* writing any
   README claim about it.
4. **`git init` and push a public repo.** Required by Nov 14.

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
