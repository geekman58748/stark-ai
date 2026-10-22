# Stark API — contract v1

**Status: frozen for the frontend.** Shapes here are what the UI may rely on. After
this point the only allowed change is **additive** (new fields, new endpoints).
Renames, removals and type changes mean bumping to `/v2`.

A runnable stub implements all of this today: `backend/server.py`. No chain, no
bill API, no AI — mock data only, so the frontend can be built in parallel.

---

## Conventions

| Rule | Detail |
|---|---|
| Base URL | `http://127.0.0.1:8000` locally. Prefix all product routes with `/v1`. |
| Money | **Integer naira**, field names end in `_ngn`. Never floats, never kobo, never strings. |
| Times | ISO 8601 UTC with a `Z` suffix, e.g. `2026-10-20T19:33:13Z`. |
| IDs | Opaque strings. Don't parse them, don't assume numeric. |
| Casing | `snake_case` everywhere. |
| CORS | Open on the stub, so any dev port works. |
| Auth | **Not implemented yet.** Device token + channel identity linking are designed in `HANDOFF.md` §8A. Assume an `Authorization: Bearer <token>` header will appear; nothing else changes. |

### Error shape

Every non-2xx response has this body:

```json
{
  "code": "over_cap",
  "message": "That would go over your monthly limit.",
  "detail": { "cap_ngn": 30000, "spent_ngn": 23000, "remaining_ngn": 7000 }
}
```

`code` is the machine-readable field — branch on it, never on `message`.

| `code` | HTTP | When |
|---|---|---|
| `unknown_bill` | 404 | No bill with that id |
| `bad_amount` | 400 | `amount_ngn` missing, zero, or not an integer |
| `bad_watts` | 400 | Telemetry `watts` not a number |
| `over_per_payment_cap` | 409 | Payment exceeds the per-payment limit |
| `over_cap` | 409 | Payment would exceed the monthly cap |
| `insufficient_balance` | 409 | Payment or withdrawal exceeds the wallet balance |
| `bad_kind` | 400 | Bill or plan `kind` is not one of the supported kinds |
| `bad_reference` | 400 | Bill reference is not 4–32 characters |
| `bad_bill` | 400 | A bill add/patch field is invalid (e.g. empty label) |
| `unsupported_product` | 400 | No confirmed vendor product for that provider |
| `plan_required` | 400 | A data/TV bill was sent without a `plan` |
| `unknown_plan` | 400 | `plan` is not a code in the vendor catalogue |
| `duplicate_bill` | 409 | That kind + reference is already saved |
| `bill_in_flight` | 409 | The bill has a pending payment; try again after it settles |
| `bad_limits` | 400 | A limit is not positive, or per-payment exceeds monthly |
| `no_route` | 404 | Unknown path |

> Ordering note: the **per-payment** cap is checked first, then the **monthly** cap,
> then the balance. An amount that breaches all three returns `over_per_payment_cap`.
> Ordering matters when the caps differ: a ₦20,000 payment with a ₦10,000
> per-payment limit returns `over_per_payment_cap`, not `over_cap`.

---

## Endpoints

### `GET /v1/state`

Everything the dashboard needs in one call. Poll or refetch after any payment.

```json
{
  "user_id": "user_tunde",
  "first_name": "Tunde",
  "currency": "NGN",
  "balance_ngn": 64200,
  "cap_ngn": 30000,
  "spent_ngn": 23000,
  "remaining_cap_ngn": 7000,
  "units_left": 11.4,
  "days_left": 4,
  "bills": [ /* Bill objects, see below */ ],
  "as_of": "2026-10-20T19:33:13Z"
}
```

`units_left` and `days_left` are `null` when the user has no electricity bill.
`days_left` is an **estimate** from purchase history until the AC sensor is wired in.

After a **delivered** payment, that bill's `last_amount_ngn`, `last_units` and
`last_paid_at` update, and `units_left` increases by the delivered units. A `pending`
or `failed` payment changes none of them. `days_left` stays the seeded estimate.

### `Bill`

```json
{
  "id": "bill_home_meter",
  "kind": "electricity",
  "provider": "Ikeja Electric",
  "label": "Home",
  "reference": "04512345678",
  "last_amount_ngn": 5000,
  "last_units": 23.9,
  "last_paid_at": "2026-10-14T19:33:13Z"
}
```

- `kind` is one of `electricity`, `airtime`, `data`, `tv`, `internet`, `water`.
- `reference` is the meter / phone / smartcard number. **Never a wallet address.**
- `plan` and `plan_price_ngn` are **additive** (2026-10-22). Data and TV are sold as
  a *plan* (a VTpass variation code such as `dstv79`), not as a free amount, so those
  bills carry the plan and its vendor price. `amount_ngn` must equal
  `plan_price_ngn` or the payment is refused — a plan is not discountable. Electricity
  and airtime have no plan and take any amount inside the owner's limits.
- `last_units` and `last_amount_ngn` are `null` for a new bill.

### `GET /v1/plans?kind=data&provider=mtn`

Every priced plan for **data** and **TV**, read from the captured VTpass catalogue.
This is the list behind the plan picker — never hardcode prices in the app, they
change at the vendor.

```json
[
  {
    "kind": "data",
    "provider": "mtn-data",
    "service_name": "MTN Data",
    "plan": "mtn-100mb-1000",
    "label": "N1000 1.5GB - 30 days",
    "price_ngn": 1000
  },
  {
    "kind": "tv",
    "provider": "dstv",
    "service_name": "DSTV Subscription",
    "plan": "dstv-padi",
    "label": "DStv Padi N1,850",
    "price_ngn": 1850
  }
]
```

Both query params are optional. `kind` must be `data` or `tv` (else `bad_kind`);
`provider` loosely matches a service id or name, so `mtn` finds `mtn-data`.
Sorted by `kind`, `provider`, then `price_ngn` ascending. `label` is the vendor's own
string — render it as-is.

### `POST /v1/bills`

Add a bill. Returns **201** with the `Bill` object.

```json
{
  "kind": "data",
  "provider": "MTN",
  "label": "My line",
  "reference": "08031234567",
  "plan": "mtn-100mb-1000"
}
```

- `kind` — `electricity`, `airtime`, `data`, `tv`, `internet`, `water`.
- `provider` — required. For `data`/`tv`/`airtime` it must resolve to a VTpass service
  (`MTN`, `mtn`, `Glo` all work); for `electricity` only **Ikeja Electric** is
  confirmed today, anything else is `unsupported_product`. `internet` and `water`
  can be saved, but paying them refuses and charges nothing.
- `reference` — meter / phone / smartcard number; whitespace is stripped, 4–32 chars.
- `label` — optional, defaults to `provider`.
- `plan` — required when the product is sold as a plan (data, DStv/GOtv/Showmax).
  Take the `plan` value from `GET /v1/plans`; the price is stored server-side as
  `plan_price_ngn`, so the client never sends a price the user could edit.
- Adding a bill updates the payer's meter allowlist immediately — the agent can pay
  the new bill in the next turn.

Errors: `bad_kind`, `bad_reference`, `unsupported_product`, `plan_required`,
`unknown_plan`, and `duplicate_bill` (same `kind` + `reference`).

### `PATCH /v1/bills/{bill_id}`

Rename a bill, or change a data/TV plan. Every field is optional; returns the full
`Bill`.

```json
{ "label": "Living room", "plan": "dstv-yanga" }
```

Changing `plan` also rewrites `plan_price_ngn`. Errors: `unknown_bill`,
`bad_bill` (empty label, or a plan on a kind that has none), `unsupported_product`,
`unknown_plan`.

### `DELETE /v1/bills/{bill_id}`

Returns `{ "deleted": true, "bill_id": "bill_abc123" }`. The bill's history stays in
`/v1/activity`.

Removing the last electricity bill sets `units_left` and `days_left` to `null` in
`/v1/state`; removing or adding any bill re-scopes the allowlist, so the agent cannot
pay a deleted bill and can pay a new one immediately.

Errors: `unknown_bill`, and `bill_in_flight` (409) while a payment for that bill is
still `pending` at the vendor.
- `last_paid_at` is `null` until first payment.

### `GET /v1/bills` → `Bill[]`

### `GET /v1/bills/{bill_id}` → `Bill`

404 `unknown_bill` if missing.

### `POST /v1/payments`

```json
{ "bill_id": "bill_home_meter", "amount_ngn": 5000 }
```

Returns **201** with a `Receipt`. Electricity adds `units` and a 20-digit `token`;
other kinds return `null` for both.

```json
{
  "id": "rcpt_3f9a1c",
  "bill_id": "bill_home_meter",
  "bill_label": "Home electricity",
  "amount_ngn": 5000,
  "units": 23.92,
  "token": "4821 0937 5512 8846 3019",
  "tx_hash": "8f2c1d4e...",
  "created_at": "2026-10-20T19:33:13Z",
  "status": "delivered",
  "request_id": "202610201930a1b2c3d4",
  "type": "bill",
  "source": "Telegram voice note"
}
```

`status` is **additive** (2026-10-22) and is the field that matters:

| `status` | Meaning | Charged? |
|---|---|---|
| `delivered` | The vendor confirmed; electricity also carries a `token` | yes |
| `pending` | Still processing at the vendor — **not** paid | no, and no token |
| `failed` | The vendor refused, or the amount was wrong; nothing was charged | no |
| `declined` | The policy gate refused it before the vendor call | no |
| `received` | Money in (a deposit), not a payment | n/a |
| `sent` | Money out (a withdrawal), not a payment | n/a |

Do not render a payment as complete unless `status` is `delivered`. Only electricity
returns a `token` — airtime, data and TV are delivered without one.
A `pending` receipt keeps its `request_id`; sending the same intent again re-queries
that purchase instead of buying a second time.

Errors: `over_per_payment_cap` (409), `over_cap` (409), `insufficient_balance` (409),
`unknown_bill` (404), `bad_amount` (400), and `vendor_failed` (502) when the bill
vendor refuses or is unreachable. Build UI for the three 409s now — they are the interesting states.
`vendor_failed` carries the vendor's plain-English line in `message`; show it, and
reassure the user that nothing was charged (that is true — charging happens only on
delivery).

`units` is `amount_ngn / tariff`, tariff ≈ ₦209/kWh, so ₦5,000 ≈ 23.9 units.

### `GET /v1/activity`

Returns up to 20 entries, newest first. Same `Receipt` shape as above.

`type` and `source` are **additive** (2026-10-22):

| `type` | Meaning | Counts as spend? |
|---|---|---|
| `bill` | A bill payment — electricity, airtime, data or TV | yes, when `delivered` |
| `autotopup` | An automatic airtime top-up | no |
| `deposit` | Money added to the wallet (`status: received`) | no |
| `withdrawal` | Money sent to a bank (`status: sent`) | no, but it lowers the balance |

`source` is the channel that asked for it (`Telegram voice note`, `Wall phone`,
`Bank transfer`) and may be `null` for entries created before this field existed.
A `declined` entry is a bill the policy gate refused before any vendor call; it is
never charged. `bill_id` is `"wallet"` for a `deposit` and a `withdrawal`.

### `GET /v1/limits`

```json
{
  "monthly_cap_ngn": 30000,
  "per_payment_cap_ngn": 10000,
  "spent_ngn": 23000,
  "remaining_cap_ngn": 7000
}
```

`remaining_cap_ngn` never goes negative. `spent_ngn` counts **delivered bill
payments only** — deposits, withdrawals, autotop-ups and declined entries do not
consume the cap.

### `PATCH /v1/limits`

Send either or both fields; returns the full object above.

```json
{ "per_payment_cap_ngn": 5000, "monthly_cap_ngn": 40000 }
```

- Each value must be a positive integer (`bad_limits`).
- The per-payment limit cannot exceed the monthly limit (`bad_limits`).
- Takes effect **immediately for the agent as well as REST payments** — the next
  voice turn is refused at the new limit, with no restart.
- Not persisted to SQLite: a restart, or `POST /v1/_stub/reset`, restores
  `₦30,000` / `₦10,000`. Do not tell a user their limit survives a reinstall until
  it is stored.

### `GET /v1/wallet`

```json
{
  "currency": "NGN",
  "balance_ngn": 64200,
  "spent_ngn": 23000,
  "monthly_cap_ngn": 30000,
  "remaining_cap_ngn": 7000,
  "added_this_month_ngn": 20000
}
```

### `POST /v1/wallet/topup`

```json
{ "amount_ngn": 20000, "request_id": "dep_7f3c1a9b2d4e", "source": "Bank transfer" }
```

Returns **201** with `{ "wallet": { /* GET /v1/wallet */ }, "entry": { /* Receipt */ } }`.
`entry.type` is `deposit`, `entry.status` is `received`, `entry.bill_id` is `"wallet"`.

- `request_id` is optional; without it the server generates one. **Send your own** for
the same reason as payments: repeating the id returns **200** with the original entry
and does not credit twice.
- `source` is free text (max 40 chars), displayed on the activity row.
- Top-ups never count towards the monthly cap.

### `POST /v1/wallet/withdraw`

```json
{ "amount_ngn": 10000, "request_id": "wd_9c2b7e4f1a6d" }
```

Returns **201** — same envelope as top-up. `entry.type` is `withdrawal`,
`entry.status` is `sent`, `entry.bill_id` is `"wallet"`.

Withdrawing lowers `balance_ngn` but **not** `spent_ngn`; the monthly cap is about
bills, not cash movement. Errors: `bad_amount`, and `insufficient_balance` (409) with
`{ balance_ngn, amount_ngn }`. Same `request_id` replay rule as top-up.

### `GET /v1/suggestions`

```json
[
  {
    "id": "sug_units",
    "text": "About 11.4 units left — roughly 4 days.",
    "severity": "warn",
    "reason": "units_low"
  }
]
```

`severity` is `info` | `warn` | `alert`. `reason` is for debugging, not display.
Copy arrives as finished sentences — render, don't reassemble.

### `POST /v1/voice`

One endpoint for Telegram, the wall phone and any future speaker.

**Accepts either:**
- `multipart/form-data` with `audio` (file, the recording) and optional `transcript_hint`
- `application/json` with `{"transcript_hint": "hello stark what's my light bill"}`

`transcript_hint` is a **stub-only** stand-in for Whisper. Real requests will send
only audio once STT lands.

```json
{
  "transcript": "hello stark what's my light bill",
  "ignored": false,
  "reply": "You've got ₦64,200 in your wallet and about 11.4 units left — roughly 4 days at this rate.",
  "token": null,
  "receipt_id": null,
  "actions": ["get_state"],
  "tx_hash": null
}
```

`actions` and `tx_hash` are **additive** (2026-10-22). `actions` lists the tools the
agent ran, which is useful for debugging a bad answer; `tx_hash` is set only when a
payment was signed onchain. Neither is user-facing copy — do not render them.

Since M2 the reply is produced by the agent: a model picks tool calls, the policy
gate checks them against the same caps the contract enforces, and `reply` comes back
already speakable. With no model key configured the server uses a deterministic
rule-based model, so the endpoint behaves and tests identically without a key.

**The wake gate is server-side.** If the transcript has no `"stark"`, the response is
`{"ignored": true, "reply": null}` and the client must stay silent. Do not play
anything on `ignored: true`.

`reply` is already speakable text — feed it straight to TTS.

### `POST /v1/telemetry`

From the AC meter bridge. Returns **202**.

```json
{ "device_id": "ac-plug-1", "watts": 1480, "ts": "2026-10-20T19:33:13Z" }
```

`ts` is optional; the server fills it. This does not feed `/v1/suggestions` yet.

### `POST /v1/tg/webhook`

Telegram's update push (M4). **The frontend does not call this** — Telegram does.
Documented so nobody exposes it or is surprised by it.

Every request must carry `X-Telegram-Bot-Api-Secret-Token` matching
`TELEGRAM_WEBHOOK_SECRET`; otherwise **401** with `webhook_unconfigured` (no
secrets set on the server) or `webhook_unverified` (wrong/missing header). It is
checked in constant time **before the body is parsed**, and the bot refuses
everything while unconfigured — there is no "open webhook" mode.

A verified update returns 200:

```json
{ "ok": true, "handled": "agent", "update_id": 918273645 }
```

`handled` is for debugging, not display: `agent` (the user asked something),
`command` (`/link`, `/whoami`, `/unlink`, `/help`), `unlinked` (linking
instructions only — the agent was never called), `asleep` (a voice note without
the word "stark"), `voice_unheard` (no STT configured), `duplicate` (a
re-delivered update — processed once), or `ignored`.

How a linked user talks to the bot: send `link 482913` (the code comes from the
app) to bind the chat, then ask in plain text or as a voice note. Voice notes go
through the same wake rule as `/v1/voice`: no "stark", no answer. Typed messages
in the DM skip it — you already know who you are talking to.

Errors: `webhook_unconfigured` (401), `webhook_unverified` (401),
`bad_update` (400, body is not JSON).

### `POST /v1/_stub/reset`

**Stub only — not part of the product contract.** Restores initial mock state so
tests and demos are repeatable: the three seed bills, units `11.4`, limits
`₦30,000` / `₦10,000`, balance `₦64,200`, spent `₦23,000`, and the six seed activity
rows. It deletes bills added during a demo. Safe to ignore from the frontend
outside a demo reset button.

---

## What is stubbed vs real

| Piece | Stub today | Real in |
|---|---|---|
| Auth | none | M4 |
| Balances | ₦64,200 seeded | M1 (vault read) |
| Payments | agent policy-checked; `tx_hash` stays `null` unless a signing key is configured | M2 — **signed and signed-only; nothing is broadcast yet** |
| Token | **vended through VTpass**, fixtures in dry-run, real when `STARK_VENDING=live` | M3 — **live credentials still missing, so no real token has ever been bought** |
| Voice | text only, `transcript_hint` | M4 (Whisper) |
| Suggestions | fixed copy | M6 (telemetry) |
| Persistence | **SQLite** (`backend/stark.db`): receipts and wallet, consistent across restarts. Bills, limits and `units_left` are in memory and reset on restart | M3 |

Shapes will not change as these land. Only the values become real.

---

## Changelog

| Date | Change |
|---|---|
| 2026-10-20 | v1 frozen. Stub implemented and smoke-tested (27 checks). |
| 2026-10-22 | M2: `/v1/voice` runs the agent loop. Additive fields `actions` and `tx_hash`. No shape changes. |
| 2026-10-22 | M3: `Receipt` gains `status` and `request_id`; new error `vendor_failed` (502). Receipts and wallet persist in SQLite. No shape changes. |
| 2026-10-22 | Product breadth: airtime, data and TV vend through confirmed VTpass services. `Bill` gains `plan` and `plan_price_ngn`. Per-payment cap 5,000 → 10,000 (a DStv bouquet is 7,900). |
| 2026-10-22 | Additive endpoints for the design's screens: `GET /v1/plans`, `POST`/`PATCH`/`DELETE /v1/bills`, `GET`/`PATCH /v1/limits`, `GET /v1/wallet`, `POST /v1/wallet/topup`, `POST /v1/wallet/withdraw`. New codes `over_per_payment_cap`, `bad_kind`, `bad_reference`, `bad_bill`, `unsupported_product`, `plan_required`, `unknown_plan`, `duplicate_bill`, `bill_in_flight`, `bad_limits`. `Receipt.type` gains `withdrawal`. No existing shape changed. |
