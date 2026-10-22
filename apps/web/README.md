# @stark/web

The marketing site for [hellostark.xyz](https://hellostark.xyz). React Router in
framework mode, Tailwind v4, pre-rendered to static HTML at build time; there is no
server at runtime.

## Commands

From the repo root:

| Command | What it does |
|---|---|
| `pnpm web` | dev server → http://localhost:5173 |
| `pnpm --filter @stark/web build` | static site → `build/client/` |
| `pnpm --filter @stark/web preview` | serve the built site on :5173 |
| `pnpm --filter @stark/web typecheck` | generate route types, then `tsc` |

## Layout

```
app/root.tsx          document shell, favicon, error boundary
app/routes.ts         route table
app/routes/home.tsx   the landing page and its meta tags
app/app.css           Tailwind entry and the colour/font tokens (bg, fg, muted, accent, accent-2)
react-router.config.ts  ssr: false + prerender: true
```

## Adding a page

1. Create `app/routes/<name>.tsx` with a default-exported component and a `meta` export.
2. Register it in `app/routes.ts`, e.g. `route("pricing", "routes/pricing.tsx")`.
3. `pnpm --filter @stark/web build` pre-renders it to `build/client/pricing/index.html`.

Because every route is pre-rendered, a page must not depend on request-time data. If one
ever needs to, that is a hosting change, not just a code change.

## Deploy

Deployed on [Brimble](https://brimble.io) from `main`:

- build command: `pnpm install && pnpm --filter @stark/web build`
- output directory: `apps/web/build/client`

## Copy rules

Product copy follows the same rules as the app: no crypto jargon (no "vault", "USDC",
addresses), and money in whole naira, e.g. `₦5,000`.
