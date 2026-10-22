# @stark/dashboard

The Stark app: balance, bills, limits, wallet and activity. A React Router SPA
(`ssr: false`) with Tailwind v4. It talks only to the backend's `/v1` API.

**Start with [`docs/FRONTEND.md`](../../docs/FRONTEND.md).** It lists every screen, the
route behind each, and the rules that matter. Exact request and response shapes are in
[`docs/API.md`](../../docs/API.md).

## Running it

The dashboard needs the backend. From the repo root, either:

```sh
pnpm dev          # web, dashboard and backend together
```

or in two shells:

```sh
pnpm backend      # http://127.0.0.1:8000
pnpm dashboard    # http://localhost:5174
```

In development, Vite proxies `/v1/*` to `http://127.0.0.1:8000`, so call the API with
relative URLs (`fetch("/v1/state")`) and it works without CORS.

| Command | What it does |
|---|---|
| `pnpm --filter @stark/dashboard build` | static SPA → `build/client/` |
| `pnpm --filter @stark/dashboard preview` | serve the build on :5174 (no `/v1` proxy) |
| `pnpm --filter @stark/dashboard typecheck` | generate route types, then `tsc` |

To get back to the seeded demo numbers (₦64,200 balance and so on):
`curl -X POST http://127.0.0.1:8000/v1/_stub/reset`.

## Layout

```
app/root.tsx          document shell and error boundary
app/routes.ts         route table
app/routes/home.tsx   placeholder home screen
app/app.css           Tailwind entry and colour/font tokens, shared with apps/web
vite.config.ts        the /v1 dev proxy
```

## Rules that bite

The full list is in `docs/FRONTEND.md` §2. The short version:

- **Branch on `code`, never on `message`.** `message` is copy and may change.
- **Money is integer naira.** Every `_ngn` field is a whole number; never divide by 100.
- **A payment is done only when `status` is `delivered`.**
- **No crypto jargon on screen, and no sliders.**
