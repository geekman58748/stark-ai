#!/usr/bin/env python3
"""Smoke test for the Stark API stub. Zero dependencies.

Start the server first:  python3 server.py
Then:                    python3 smoke_test.py

Exits 0 if every check passes, 1 otherwise. Order matters: the payment
checks mutate in-memory state, so run it against a freshly started server.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
failures: list[str] = []
checks = 0


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict | list, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        # 15s, not 5: a /v1/voice reply may be spoken server-side (TTS
        # sidecar) on top of the agent turn, and neither should hit the ceiling.
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read() or b"null"), dict(resp.headers)
    except urllib.error.HTTPError as err:
        raw = err.read()
        return err.code, (json.loads(raw) if raw else {}), dict(err.headers)


def check(name: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}{(' — ' + detail) if detail else ''}")
        failures.append(name)


print("Stark API stub — smoke test\n")

# Make the run repeatable regardless of prior payments.
call("POST", "/v1/_stub/reset")

# --- read endpoints ---------------------------------------------------------
status, index, _ = call("GET", "/")
check("GET / lists routes", status == 200 and len(index.get("routes", [])) == 21,
      f"status={status}")

status, health, _ = call("GET", "/health")
check("GET /health ok", status == 200 and health.get("status") == "ok", f"status={status}")

status, st, _ = call("GET", "/v1/state")
check("GET /v1/state 200", status == 200, f"status={status}")
check("state balance is 64200", st.get("balance_ngn") == 64200, str(st.get("balance_ngn")))
check("state cap is 30000", st.get("cap_ngn") == 30000, str(st.get("cap_ngn")))
check("state has 3 bills", len(st.get("bills", [])) == 3, str(len(st.get("bills", []))))

status, bills, _ = call("GET", "/v1/bills")
check("GET /v1/bills 200", status == 200 and len(bills) == 3, f"status={status}")

status, bill, _ = call("GET", "/v1/bills/bill_home_meter")
check("bill detail is electricity", status == 200 and bill.get("kind") == "electricity")

status, missing, _ = call("GET", "/v1/bills/nope")
check("unknown bill -> 404 unknown_bill",
      status == 404 and missing.get("code") == "unknown_bill", f"status={status}")

# --- plans, add/remove bill ------------------------------------------------
status, plans, _ = call("GET", "/v1/plans?kind=tv")
check("GET /v1/plans 200", status == 200 and len(plans) > 0, f"status={status}")
dstv79 = next((p for p in plans if p.get("plan") == "dstv79"), {})
check("dstv79 costs 7900", dstv79.get("price_ngn") == 7900, str(dstv79))

# A picker's provider chip says "MTN" / "mtn", not "mtn-data".
status, mtn, _ = call("GET", "/v1/plans?kind=data&provider=MTN")
check("plans provider filter is loose",
      status == 200 and len(mtn) > 0 and all(p.get("provider") == "mtn-data" for p in mtn),
      f"status={status} n={len(mtn)}")

new_bill = {"kind": "tv", "provider": "DStv", "label": "Test TV",
            "reference": "9998887776", "plan": "dstv79"}
status, added, _ = call("POST", "/v1/bills", new_bill)
check("POST /v1/bills 201", status == 201, f"status={status} {added}")
check("added bill carries plan price", added.get("plan_price_ngn") == 7900, str(added))
status, dup, _ = call("POST", "/v1/bills", new_bill)
check("duplicate bill -> 409",
      status == 409 and dup.get("code") == "duplicate_bill",
      f"status={status} {dup.get('code')}")
status, patched, _ = call("PATCH", f"/v1/bills/{added.get('id')}", {"plan": "dstv-padi"})
check("PATCH plan -> 1850",
      status == 200 and patched.get("plan_price_ngn") == 1850,
      f"status={status} {patched}")
status, deleted, _ = call("DELETE", f"/v1/bills/{added.get('id')}")
check("DELETE bill -> 200",
      status == 200 and deleted.get("deleted") is True, f"status={status} {deleted}")
status, gone, _ = call("GET", f"/v1/bills/{added.get('id')}")
check("deleted bill -> 404",
      status == 404 and gone.get("code") == "unknown_bill", f"status={status}")

status, sugg, _ = call("GET", "/v1/suggestions")
check("suggestions returns 2", status == 200 and len(sugg) == 2, f"status={status}")

status, activity, _ = call("GET", "/v1/activity")
check("activity seeded with 6", status == 200 and len(activity) == 6, f"status={status}")

# --- payments ---------------------------------------------------------------
status, receipt, _ = call("POST", "/v1/payments",
                          {"bill_id": "bill_home_meter", "amount_ngn": 5000})
check("pay 5000 -> 201", status == 201, f"status={status}")
check("receipt has token", bool(receipt.get("token")), str(receipt))
check("units = 5000 / 209", receipt.get("units") == 23.92, str(receipt.get("units")))

status, st2, _ = call("GET", "/v1/state")
check("balance dropped to 59200", st2.get("balance_ngn") == 59200, str(st2.get("balance_ngn")))
check("spent rose to 28000", st2.get("spent_ngn") == 28000, str(st2.get("spent_ngn")))

home = next((b for b in st2.get("bills", []) if b.get("id") == "bill_home_meter"), {})
check("bill last amount updated", home.get("last_amount_ngn") == 5000, str(home))
check("bill last units updated", home.get("last_units") == 23.92, str(home.get("last_units")))
check("bill last paid updated", home.get("last_paid_at") == receipt.get("created_at"),
      str(home.get("last_paid_at")))
check("units left rose to 35.32", st2.get("units_left") == 35.32, str(st2.get("units_left")))

status, _, _ = call("POST", "/v1/payments", {"bill_id": "bill_home_meter", "amount_ngn": 1000})
check("second pay 1000 -> 201", status == 201, f"status={status}")

status, over, _ = call("POST", "/v1/payments",
                       {"bill_id": "bill_home_meter", "amount_ngn": 20000})
check("over per-payment -> 409 over_per_payment_cap",
      status == 409 and over.get("code") == "over_per_payment_cap",
      f"status={status} {over.get('code')}")
check("over per-payment states cap",
      over.get("detail", {}).get("cap_ngn") == 10000, str(over.get("detail")))

status, over, _ = call("POST", "/v1/payments",
                       {"bill_id": "bill_home_meter", "amount_ngn": 2000})
check("over cap -> 409 over_cap",
      status == 409 and over.get("code") == "over_cap", f"status={status} {over.get('code')}")
check("over_cap states remaining", over.get("detail", {}).get("remaining_ngn") == 1000,
      str(over.get("detail")))

status, bad, _ = call("POST", "/v1/payments", {"bill_id": "bill_nope", "amount_ngn": 1000})
check("unknown bill payment -> 404", status == 404 and bad.get("code") == "unknown_bill")

status, zero, _ = call("POST", "/v1/payments", {"bill_id": "bill_home_meter", "amount_ngn": 0})
check("zero amount -> 400 bad_amount",
      status == 400 and zero.get("code") == "bad_amount", f"status={status}")

# The agent's default top-up is ₦5,000; reset so it still fits the monthly cap.
call("POST", "/v1/_stub/reset")

# --- voice ------------------------------------------------------------------
status, answer, _ = call("POST", "/v1/voice", {"transcript_hint": "hello stark what's my light bill"})
check("voice query answers with units",
      status == 200 and "units left" in (answer.get("reply") or ""), str(answer.get("reply")))

status, ig, _ = call("POST", "/v1/voice", {"transcript_hint": "what time is it"})
check("no wake word -> ignored", status == 200 and ig.get("ignored") is True)

status, pay, _ = call("POST", "/v1/voice", {"transcript_hint": "hello stark top it up"})
check("voice pay returns token", status == 200 and bool(pay.get("token")))

# The reply comes back spoken when the TTS sidecar is up (STARK_TTS_URL), and
# the additive `audio` field is present either way — null when voice is off.
import base64                                       # noqa: E402 - section-local

audio_field = answer.get("audio", "missing")
check("voice reply carries audio field", audio_field != "missing")
check("audio is a WAV data URL or null",
      audio_field is None or (
          isinstance(audio_field, str)
          and audio_field.startswith("data:audio/wav;base64,")
      ), str(audio_field)[:60])
if isinstance(audio_field, str) and audio_field.startswith("data:audio/wav;base64,"):
    spoken = base64.b64decode(audio_field.split(",", 1)[1])
    check("sidecar audio decodes to a real WAV",
          spoken[:4] == b"RIFF" and len(spoken) > 1000, f"len={len(spoken)}")
check("ignored reply never carries audio", ig.get("audio") is None, str(ig.get("audio"))[:40])

# --- limits and wallet ------------------------------------------------------
status, limits, _ = call("GET", "/v1/limits")
check("GET /v1/limits",
      status == 200 and limits.get("monthly_cap_ngn") == 30000
      and limits.get("per_payment_cap_ngn") == 10000, str(limits))
status, limits2, _ = call("PATCH", "/v1/limits",
                          {"monthly_cap_ngn": 40000, "per_payment_cap_ngn": 15000})
check("PATCH /v1/limits",
      status == 200 and limits2.get("monthly_cap_ngn") == 40000
      and limits2.get("per_payment_cap_ngn") == 15000, str(limits2))
status, st3, _ = call("GET", "/v1/state")
check("state cap follows limits", st3.get("cap_ngn") == 40000, str(st3.get("cap_ngn")))

status, wallet, _ = call("GET", "/v1/wallet")
check("GET /v1/wallet",
      status == 200 and wallet.get("added_this_month_ngn") == 20000, str(wallet))
before = int(wallet.get("balance_ngn") or 0)
status, topup, _ = call("POST", "/v1/wallet/topup", {"amount_ngn": 5000})
check("topup credits",
      status == 201 and topup.get("wallet", {}).get("balance_ngn") == before + 5000,
      f"status={status} {topup.get('wallet')}")
status, withdraw, _ = call("POST", "/v1/wallet/withdraw", {"amount_ngn": 1000})
check("withdraw debits",
      status == 201 and withdraw.get("wallet", {}).get("balance_ngn") == before + 4000,
      f"status={status} {withdraw.get('wallet')}")
status, poor, _ = call("POST", "/v1/wallet/withdraw", {"amount_ngn": before + 4001})
check("over-withdraw -> 409",
      status == 409 and poor.get("code") == "insufficient_balance",
      f"status={status} {poor.get('code')}")

# --- telemetry, telegram, cors ---------------------------------------------
status, tel, _ = call("POST", "/v1/telemetry", {"device_id": "ac-plug-1", "watts": 1480})
check("telemetry accepted", status == 202 and tel.get("accepted") is True, f"status={status}")

# The Telegram webhook must refuse an unauthenticated update, whether or not the
# bot is configured — a missing header is 401 in both worlds, so this is testable
# without any secret. (§8A: verify before parsing.)
def raw_call(path: str, body: dict, headers: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as err:
        raw = err.read()
        return err.code, (json.loads(raw) if raw else {})

status, tg = raw_call("/v1/tg/webhook", {"update_id": 42}, {})
check("telegram webhook without secret -> 401",
      status == 401 and tg.get("code") in ("webhook_unconfigured", "webhook_unverified"),
      f"status={status} {tg.get('code')}")
status, tg = raw_call("/v1/tg/webhook", {"update_id": 42},
                      {"X-Telegram-Bot-Api-Secret-Token": "definitely-wrong"})
check("telegram webhook with wrong secret -> 401",
      status == 401 and tg.get("code") in ("webhook_unconfigured", "webhook_unverified"),
      f"status={status} {tg.get('code')}")

status, _, headers = call("GET", "/v1/state")
check("CORS header present", headers.get("Access-Control-Allow-Origin") == "*",
      str(headers.get("Access-Control-Allow-Origin")))

# Leave the demo seeded even when the run is used interactively.
call("POST", "/v1/_stub/reset")

print(f"\n{checks - len(failures)}/{checks} checks passed")
if failures:
    print("failed: " + ", ".join(failures))
    sys.exit(1)
print("all good")
