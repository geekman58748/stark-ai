# @stark/website

The marketing site for [hellostark.xyz](https://hellostark.xyz). React Router in
framework mode, Tailwind v4, pre-rendered to static HTML at build time; there is no
server at runtime. Tokens, fonts, icons and the logo come from [`@stark/ui`](../../packages/ui).

## Commands

From the repo root:

| Command | What it does |
|---|---|
| `bun dev:website` | dev server → http://localhost:5173 |
| `bun build:website` | static site → `apps/website/build/client/` |
| `bun start:website` | serve the built site on :5173 |
| `bun --filter @stark/website typecheck` | generate route types, then `tsc` |

## Layout

```
app/root.tsx            document shell, favicon, error boundary
app/routes.ts           route table
app/routes/home.tsx     the landing page and its meta tags
app/components/         one file per landing-page section (hero, statement, safety, …)
app/lib/links.ts        where the CTAs point (dashboard, Telegram bot)
app/app.css             Tailwind entry, @stark/ui tokens, the `swash` marker utility
react-router.config.ts  ssr: false + prerender: true
```

## Environment

| Variable | Default | Used for |
|---|---|---|
| `VITE_DASHBOARD_URL` | `http://localhost:5174` | "Get started", "Log in" and Talk links. **Set it in Brimble**, or production links point at localhost |
| `VITE_TELEGRAM_BOT_URL` | falls back to the dashboard | "Open the Telegram bot" |

## Adding a page

1. Create `app/routes/<name>.tsx` with a default-exported component and a `meta` export.
2. Register it in `app/routes.ts`, e.g. `route("pricing", "routes/pricing.tsx")`.
3. `bun build:website` pre-renders it to `build/client/pricing/index.html`.

Because every route is pre-rendered, a page must not depend on request-time data. If one
ever needs to, that is a hosting change, not just a code change.

## Deploy

Deployed on [Brimble](https://brimble.io) from `main`:

- build command: `bun install && bun build:website`
- output directory: `apps/website/build/client`

## Copy rules

Product copy follows the same rules as the app: no crypto jargon (no "vault", "USDC",
addresses), and money in whole naira, e.g. `₦5,000`.
