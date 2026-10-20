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
        with urllib.request.urlopen(req, timeout=5) as resp:
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
check("GET / lists routes", status == 200 and len(index.get("routes", [])) == 12,
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

status, sugg, _ = call("GET", "/v1/suggestions")
check("suggestions returns 2", status == 200 and len(sugg) == 2, f"status={status}")

status, activity, _ = call("GET", "/v1/activity")
check("activity seeded with 3", status == 200 and len(activity) == 3, f"status={status}")

# --- payments ---------------------------------------------------------------
status, receipt, _ = call("POST", "/v1/payments",
                          {"bill_id": "bill_home_meter", "amount_ngn": 5000})
check("pay 5000 -> 201", status == 201, f"status={status}")
check("receipt has token", bool(receipt.get("token")), str(receipt))
check("units = 5000 / 209", receipt.get("units") == 23.92, str(receipt.get("units")))

status, st2, _ = call("GET", "/v1/state")
check("balance dropped to 59200", st2.get("balance_ngn") == 59200, str(st2.get("balance_ngn")))
check("spent rose to 17400", st2.get("spent_ngn") == 17400, str(st2.get("spent_ngn")))

status, _, _ = call("POST", "/v1/payments", {"bill_id": "bill_home_meter", "amount_ngn": 5000})
check("second pay 5000 -> 201", status == 201, f"status={status}")

status, over, _ = call("POST", "/v1/payments",
                       {"bill_id": "bill_home_meter", "amount_ngn": 20000})
check("over cap -> 409 over_cap",
      status == 409 and over.get("code") == "over_cap", f"status={status} {over.get('code')}")
check("over_cap states remaining", over.get("detail", {}).get("remaining_ngn") == 7600,
      str(over.get("detail")))

status, bad, _ = call("POST", "/v1/payments", {"bill_id": "bill_nope", "amount_ngn": 1000})
check("unknown bill payment -> 404", status == 404 and bad.get("code") == "unknown_bill")

status, zero, _ = call("POST", "/v1/payments", {"bill_id": "bill_home_meter", "amount_ngn": 0})
check("zero amount -> 400 bad_amount",
      status == 400 and zero.get("code") == "bad_amount", f"status={status}")

# --- voice ------------------------------------------------------------------
status, answer, _ = call("POST", "/v1/voice", {"transcript_hint": "hello stark what's my light bill"})
check("voice query answers with units",
      status == 200 and "units left" in (answer.get("reply") or ""), str(answer.get("reply")))

status, ig, _ = call("POST", "/v1/voice", {"transcript_hint": "what time is it"})
check("no wake word -> ignored", status == 200 and ig.get("ignored") is True)

status, pay, _ = call("POST", "/v1/voice", {"transcript_hint": "hello stark top it up"})
check("voice pay returns token", status == 200 and bool(pay.get("token")))

# --- telemetry, telegram, cors ---------------------------------------------
status, tel, _ = call("POST", "/v1/telemetry", {"device_id": "ac-plug-1", "watts": 1480})
check("telemetry accepted", status == 202 and tel.get("accepted") is True, f"status={status}")

status, tg, _ = call("POST", "/v1/tg/webhook", {"update_id": 42})
check("telegram webhook ok", status == 200 and tg.get("ok") is True)

status, _, headers = call("GET", "/v1/state")
check("CORS header present", headers.get("Access-Control-Allow-Origin") == "*",
      str(headers.get("Access-Control-Allow-Origin")))

print(f"\n{checks - len(failures)}/{checks} checks passed")
if failures:
    print("failed: " + ", ".join(failures))
    sys.exit(1)
print("all good")
