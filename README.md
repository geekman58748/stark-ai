# Stark

An AI agent that pays your everyday bills from a crypto balance, within limits you
set, by voice or chat. Starts with Nigerian prepaid electricity; covers airtime,
data, TV, internet and water. Built for **NEAR HACKATHON** (2026-11-01 → 11-14).

- Tracks: `realworld` (lead), `security`, `agents`
- Design source (the exported artboards) lives outside the repo; ask a maintainer for access

## Quick start

You need **Node 22+** (24 recommended, see `.nvmrc`), **Bun 1.3+** and **Python 3.9+**.
Nothing else: the backend has no Python dependencies, and Rust is only needed if you
change the contract.

```sh
bun install
bun dev                       # website, dashboard and backend together
```

| App | URL |
|---|---|
| Marketing site | http://localhost:5173 |
| Dashboard | http://localhost:5174 |
| API | http://127.0.0.1:8000 |

Everything runs offline with no configuration: payments are dry-run, nothing touches a
chain, and a deterministic model stands in for the LLM. To switch real services on, copy
[`apps/backend/.env.example`](apps/backend/.env.example) to `apps/backend/.env`.

Check that it all works:

```sh
bun check                     # typecheck + lint + backend unit tests
bun smoke                     # 50 end-to-end checks; needs the backend running
```

### Troubleshooting

- **`Address already in use`.** Something else holds a port (often an old backend).
  `lsof -nP -iTCP:8000 -sTCP:LISTEN` shows what; stop it and rerun. Under `bun dev`
  one app failing stops the others, so check the first error in the output.
- **Dashboard shows no data.** The backend is not running, or is on a different port;
  the dashboard only proxies `/v1` to `127.0.0.1:8000`.
- **`bun: command not found`.** Install it with `curl -fsSL https://bun.sh/install | bash`.
- **Demo numbers drifted.** `curl -X POST http://127.0.0.1:8000/v1/_stub/reset`.

## What's in the repo

A Bun + Turborepo monorepo, laid out like [midday](https://github.com/midday-ai/midday). Each app
has its own README; start there when you work on it.

| Path | What it is | Stack |
|---|---|---|
| [`apps/website`](apps/website) | marketing site for hellostark.xyz | React Router, pre-rendered static HTML |
| [`apps/dashboard`](apps/dashboard) | the Stark app users manage bills in | TanStack Start (SPA) + TanStack Query |
| [`apps/backend`](apps/backend) | API, agent, bill vending, Telegram bot | Python, standard library only |
| [`apps/contracts`](apps/contracts) | NEAR vault contract: caps and allowlist | Rust, near-sdk |
| [`packages/ui`](packages/ui) | shared tokens, fonts, icons and components | Tailwind v4, Reicon |
| [`packages/api`](packages/api) | typed `/v1` client, query options and mutations | TanStack Query |
| [`packages/utils`](packages/utils) | naira and date formatting, request ids | |
| [`docs`](docs) | the API contract, frontend guide, backend handoff | |

Which doc to read first:

- **Building the web app or dashboard?** [`docs/FRONTEND.md`](docs/FRONTEND.md): every
  screen, the route behind it, and the rules that matter.
- **Working on the backend?** [`docs/HANDOFF.md`](docs/HANDOFF.md): environment traps,
  what is verified versus guessed, and what to do next.
- **Calling the API?** [`docs/API.md`](docs/API.md) is the contract. It is frozen.

## Scripts

Run from the repo root.

| Command | What it does |
|---|---|
| `bun dev` | all three apps in parallel |
| `bun dev:website` / `bun dev:dashboard` / `bun dev:backend` | one app on its own |
| `bun run build` | build the website and dashboard |
| `bun typecheck` | TypeScript across the workspace |
| `bun lint` / `bun format` | Biome |
| `bun run test` | backend unit tests (149, hermetic) |
| `bun check` | typecheck + lint + test, what CI should run |
| `bun smoke` | end-to-end checks against a running backend |

Contract commands are in [`apps/contracts`](apps/contracts/README.md); they need a Rust
toolchain, so they are not part of `bun run test`.

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

## Deploy

The marketing site deploys to [hellostark.xyz](https://hellostark.xyz) on
[Brimble](https://brimble.io) from `main`; see [`apps/website`](apps/website/README.md#deploy).
Nothing else is deployed yet.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).
