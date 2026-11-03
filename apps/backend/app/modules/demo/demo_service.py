"""A sample account anyone can look at, without signing up.

Built in memory from the artboard seed on every read, so it never touches the
database and never shows a real person's meter or line: the numbers are made up
and labelled as such by the page that shows them. Timestamps move with the clock,
so the sample always has a renewal due and a request still waiting.
"""

from __future__ import annotations

from typing import Any

from app.common.clock import Clock
from app.modules.receipt import receipt_repository
from app.modules.reminder import reminders
from app.modules.stub.stub_seed import StubSeed

MONTHLY_CAP_NGN = 30_000
PER_PAYMENT_CAP_NGN = 10_000


class DemoService:
    def snapshot(self) -> dict[str, Any]:
        bills = StubSeed.bills()
        # The seed's declined ₦15,000 predates approvals: over a limit, Stark asks
        # now, so the sample shows that attempt waiting on the owner instead.
        history = [r for r in StubSeed.receipts(bills) if r["status"] != "declined"]
        StubSeed.sync_history(bills, history)
        return {
            "state": {
                "user_id": "demo",
                "first_name": "Tunde",
                "currency": "NGN",
                "balance_ngn": StubSeed.BALANCE_NGN,
                "cap_ngn": MONTHLY_CAP_NGN,
                "spent_ngn": StubSeed.SPENT_NGN,
                "remaining_cap_ngn": MONTHLY_CAP_NGN - StubSeed.SPENT_NGN,
                "paused": False,
                "units_left": 11.4,
                "days_left": 4,
                "bills": list(bills.values()),
                "due_soon": reminders.due_soon(bills.values()),
                "as_of": Clock.now_iso(),
            },
            "activity": [receipt_repository.api_shape(r) for r in history],
            "approvals": [{
                "id": "req_demo",
                "bill_id": "bill_home_meter",
                "bill_label": "Home electricity",
                "amount_ngn": 15_000,
                "reason": "over_per_payment_cap",
                "status": "pending",
                "created_at": Clock.ago(minutes=17),
                "expires_at": Clock.in_minutes(43),
                "decided_at": None,
                "receipt_id": None,
            }],
            "limits": {
                "monthly_cap_ngn": MONTHLY_CAP_NGN,
                "per_payment_cap_ngn": PER_PAYMENT_CAP_NGN,
            },
        }
