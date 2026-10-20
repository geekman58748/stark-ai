# VTpass fixtures

Two kinds of file in here. The distinction matters — don't blur it.

## Captured live

- **`service-variations_ikeja-electric.json`** — fetched 2026-10-20 from
  `https://sandbox.vtpass.com/api/service-variations?serviceID=ikeja-electric`.
  HTTP 200, 538 bytes, no credentials required. This is the real response body,
  including VTpass's own misspelling of `variations` as `varations`.

## Modeled on the documented shape — NOT captured

The rest were written by hand to match VTpass's documented response structure and
the response-code table published in their SDK. They have **never been seen from
the live API**, because `merchant-verify` and `pay` both require credentials we
don't have yet.

| File | Represents |
|---|---|
| `merchant-verify_ok.json` | Meter found, customer name returned |
| `pay_ok.json` | Token vended, `status: delivered` |
| `pay_pending.json` | `code: 099`, `status: pending`, no token yet |
| `pay_low_balance.json` | `code: 018`, VTpass wallet too low |
| `pay_duplicate.json` | `code: 019`, same `request_id` reused |

Once real credentials exist, run `python3 vtpass.py --live verify --meter ...`
and `--live buy ...`, then replace these with actual captured bodies. Until then,
treat every hand-written field name as a guess: `Customer_Name` in particular may
be cased or named differently in reality.

Response codes used here come from VTpass's published enum:
`000` success, `011` invalid args, `012` product not found, `018` low balance,
`019` duplicate, `020` biller confirmed, `030` unreachable, `034` suspended,
`083` system error, `099` processing.
