# Contributing to Stark

Thanks for helping. This file covers how to get set up, how work flows, and what a pull
request needs. Product context and the app map are in the [README](README.md).

## Setup

```sh
corepack enable
pnpm install
pnpm dev          # web :5173, dashboard :5174, API :8000
```

Requirements: Node 22+ (`.nvmrc` says 24), pnpm 11 (pinned via `packageManager`),
Python 3.9+. Rust only if you touch [`apps/contracts`](apps/contracts/README.md).

Configuration is per app. Only the backend reads any today:
`cp apps/backend/.env.example apps/backend/.env`. Never commit a `.env`; they are
gitignored.

## Making a change

1. Branch from `main`: `feat/bill-reminders`, `fix/dashboard-cap-rounding`.
2. Read the README of the app you are changing. The rules there are not optional.
3. Keep a change to one concern. A UI change and an API change are two pull requests
   unless one cannot land without the other.
4. Before pushing, run:

   ```sh
   pnpm check        # typecheck + backend unit tests
   pnpm build        # web and dashboard build
   pnpm smoke        # if you touched the backend: start it first with `pnpm backend`
   ```

   If you changed the contract, also run `pnpm --filter @stark/contracts contract:test`.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org):

```
type(scope): imperative summary in lowercase

Why the change was needed, wrapped at ~72-100 characters.
```

- `type`: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`
- `scope`: the app or area, e.g. `web`, `dashboard`, `backend`, `contracts`, `docs`

Example: `fix(backend): reuse request_id when retrying a pending vend`.

## Pull requests

- Say what changed and why, and how you verified it. Screenshots for any visible UI change.
- Link the issue or milestone (M0–M7 in the README) it moves forward.
- CI-equivalent is `pnpm check && pnpm build`; a PR that fails either is not ready.

## Rules that apply everywhere

- **The API contract in [`docs/API.md`](docs/API.md) is frozen.** Additive changes only.
  A rename or type change means `/v2`. Update `API.md` in the same PR as the code.
- **Money is integer naira.** No floats, no kobo.
- **Branch on error `code`, never on `message`.**
- **No crypto jargon in user-facing copy** ("vault", "USDC", addresses), and **no sliders**.
- **Never commit secrets.** Keys go in env vars.
- **`apps/backend/policy.py` mirrors `apps/contracts/vault/src/policy.rs`.** Change both
  together; a test fails if they drift.
- **Payments stay dry-run by default.** Anything that vends, signs or broadcasts for real
  must be switched on by an env var, and must refuse to start when misconfigured.
