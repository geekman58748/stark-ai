# VTpass fixtures

Two kinds of file in here. The distinction matters — don't blur it.

## Captured live

Fetched from `https://sandbox.vtpass.com`. All of these are public catalogue
endpoints — no credentials required, HTTP 200, stored as the real response body,
including VTpass's own misspelling of `variations` as `varations` where it appears.

**2026-10-20**

- `service-variations_ikeja-electric.json` —
  `/api/service-variations?serviceID=ikeja-electric`

**2026-10-22** — the product catalogue that `catalog.py` reads

| File | Source |
|---|---|
| `services_airtime.json` | `/api/services?identifier=airtime` — `mtn`, `airtel`, `glo`, `etisalat`, `foreign-airtime` |
| `services_data.json` | `/api/services?identifier=data` — `mtn-data`, `airtel-data`, `glo-data`, `etisalat-data`, `smile-direct`, `spectranet`, `glo-sme-data` |
| `services_tv-subscription.json` | `/api/services?identifier=tv-subscription` — `dstv`, `gotv`, `startimes`, `showmax` |
| `service-variations_mtn-data.json` | 37 MTN data bundles |
| `service-variations_airtel-data.json` | 26 Airtel bundles |
| `service-variations_glo-data.json` | 79 Glo bundles |
| `service-variations_etisalat-data.json` | 18 9mobile bundles |
| `service-variations_dstv.json` | 67 DStv bouquets (`dstv79` = Compact, ₦7,900) |
| `service-variations_gotv.json` | 7 GOtv bouquets |
| `service-variations_startimes.json` | 25 Startimes bouquets |
| `service-variations_showmax.json` | 11 Showmax plans |
| `service-variations_mtn.json` | `011 No Variations for MTN Airtime VTU` — the proof airtime is billed by amount, not by plan |

Two facts from that capture worth keeping in mind:

- **`identifier=electricity` and `identifier=internet` return
  `011 Category Does not Exist`.** Electricity is addressed by DISCO service id
  (`ikeja-electric`) instead.
- **`startimes` is `product_type: flexible` and still has 25 priced bouquets.** The
  plan list, not `product_type`, decides whether a product is amount-priced.

## Modeled on the documented shape — NOT captured

These were written by hand to match VTpass's documented response structure and the
response-code table published in their SDK. They cover **purchase** responses, which
need credentials we do not have, so they have never been seen from the live API.

| File | Represents |
|---|---|
| `merchant-verify_ok.json` | Meter found, customer name returned |
| `pay_ok.json` | Token vended, `status: delivered` |
| `pay_pending.json` | `code: 099`, `status: pending`, no token yet |
| `pay_low_balance.json` | `code: 018`, VTpass wallet too low |
| `pay_duplicate.json` | `code: 019`, same `request_id` reused |

Once real credentials exist, run `python3 vtpass.py --live verify --meter ...` and
`--live buy ...`, then replace these with actual captured bodies. Until then, treat
every hand-written field name as a guess: `Customer_Name` in particular may be cased
or named differently in reality. **`pay_ok.json` is also the demo's only token**, so
every dry-run purchase returns `4821 0937 5512 8846 3019` — never present that as a
live purchase.

Response codes used here come from VTpass's published enum:
`000` success, `011` invalid args, `012` product not found, `018` low balance,
`019` duplicate, `020` biller confirmed, `030` unreachable, `034` suspended,
`083` system error, `099` processing.
