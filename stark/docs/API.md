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
| Auth | **Not implemented yet.** Device token + Telegram mapping land in M4. Assume an `Authorization: Bearer <token>` header will appear; nothing else changes. |

### Error shape

Every non-2xx response has this body:

```json
{
  "code": "over_cap",
  "message": "That would go over your monthly limit.",
  "detail": { "cap_ngn": 30000, "spent_ngn": 22400, "remaining_ngn": 7600 }
}
```

`code` is the machine-readable field — branch on it, never on `message`.

| `code` | HTTP | When |
|---|---|---|
| `unknown_bill` | 404 | No bill with that id |
| `bad_amount` | 400 | `amount_ngn` missing, zero, or not an integer |
| `bad_watts` | 400 | Telemetry `watts` not a number |
| `over_cap` | 409 | Payment would exceed the monthly cap |
| `insufficient_balance` | 409 | Payment exceeds wallet balance |
| `no_route` | 404 | Unknown path |

> Ordering note: the cap is checked **before** the balance, so an amount that
> breaches both returns `over_cap`.

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
  "spent_ngn": 12400,
  "remaining_cap_ngn": 17600,
  "units_left": 11.4,
  "days_left": 4,
  "bills": [ /* Bill objects, see below */ ],
  "as_of": "2026-10-20T19:33:13Z"
}
```

`units_left` and `days_left` are `null` when the user has no electricity bill.
`days_left` is an **estimate** from purchase history until the AC sensor is wired in.

### `Bill`

```json
{
  "id": "bill_home_meter",
  "kind": "electricity",
  "provider": "Ikeja Electric",
  "label": "Home meter",
  "reference": "04512345678",
  "last_amount_ngn": 5000,
  "last_units": 23.9,
  "last_paid_at": "2026-10-14T19:33:13Z"
}
```

- `kind` is one of `electricity`, `airtime`, `data`, `tv`, `internet`, `water`.
- `reference` is the meter / phone / smartcard number. **Never a wallet address.**
- `last_units` and `last_amount_ngn` are `null` for a new bill.
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
  "bill_label": "Home meter",
  "amount_ngn": 5000,
  "units": 23.92,
  "token": "4821 0937 5512 8846 3019",
  "tx_hash": "8f2c1d4e...",
  "created_at": "2026-10-20T19:33:13Z"
}
```

Errors: `over_cap` (409), `insufficient_balance` (409), `unknown_bill` (404),
`bad_amount` (400). Build UI for the two 409s now — they are the interesting states.

`units` is `amount_ngn / tariff`, tariff ≈ ₦209/kWh, so ₦5,000 ≈ 23.9 units.

### `GET /v1/activity`

Returns up to 20 receipts, newest first. Same `Receipt` shape as above.

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
  "receipt_id": null
}
```

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

Telegram updates. Returns `{"ok": true, "stub": true, ...}` until M4.

### `POST /v1/_stub/reset`

**Stub only — not part of the product contract.** Restores initial mock state so
tests and demos are repeatable. Safe to ignore from the frontend.

---

## What is stubbed vs real

| Piece | Stub today | Real in |
|---|---|---|
| Auth | none | M4 |
| Balances | fixed ₦64,200, in memory | M1 (vault read) |
| Payments | fake `tx_hash`, never signed | M2 |
| Token | a fixed sample string | M3 (VTpass) |
| Voice | text only, `transcript_hint` | M4 (Whisper) |
| Suggestions | fixed copy | M6 (telemetry) |
| Persistence | in memory, resets on restart | M3 (SQLite) |

Shapes will not change as these land. Only the values become real.

---

## Changelog

| Date | Change |
|---|---|
| 2026-10-20 | v1 frozen. Stub implemented and smoke-tested (27 checks). |
