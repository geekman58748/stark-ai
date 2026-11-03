"""Bachs's event push: verify, de-duplicate, hand to whoever owns the money.

| Event | Goes to |
|---|---|
| `collection.succeeded`, `collection.failed` | `DepositService.on_collection` |
| `payout.paid`, `payout.failed` | the float (`refill_…`) or a withdrawal (`wd_…`) |
| anything else | acknowledged and ignored |

The signature is checked on the raw bytes before anything parses them. Delivery is
at least once, so the event id is recorded in `processed_messages` *after* it has
been handled: a crash halfway lets Bachs's retry finish the job, and every handler
is idempotent on its own reference anyway.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from app.common.api_error import ApiError
from app.common.clock import Clock
from app.database import neon
from app.modules.bachs import bachs
from app.modules.liquidity.float_service import FloatService
from app.modules.wallet.deposit_service import DepositService
from app.modules.wallet.withdrawal_service import WithdrawalService


class BachsWebhookService:
    def __init__(
        self,
        db: neon.Database,
        secret: Optional[str],
        deposits: DepositService,
        withdrawals: WithdrawalService,
        floats: FloatService,
    ) -> None:
        self.db = db
        self.secret = secret
        self.deposits = deposits
        self.withdrawals = withdrawals
        self.floats = floats

    def handle(self, raw: bytes, headers: Mapping[str, str]) -> dict[str, Any]:
        if not self.secret:
            raise ApiError(
                401, "webhook_unconfigured", "BACHS_WEBHOOK_SECRET is not set"
            )
        if not bachs.verify_signature(raw, headers, self.secret):
            raise ApiError(401, "webhook_unverified", "Bad or stale signature")
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as err:
            raise ApiError(400, "bad_update", "Body is not JSON") from err

        event_id = event["id"]
        if (
            self.db.one(
                "SELECT 1 AS seen FROM processed_messages WHERE channel = 'bachs'"
                " AND message_id = $1",
                [event_id],
            )
            is not None
        ):
            return {"ok": True, "duplicate": True}

        event_type = event["type"]
        data = event.get("data") or {}
        if event_type in ("collection.succeeded", "collection.failed"):
            self.deposits.on_collection(event_type, data)
        elif event_type in ("payout.paid", "payout.failed"):
            reference = data.get("reference") or ""
            paid = event_type == "payout.paid"
            if not self.floats.on_payout(reference, paid):
                self.withdrawals.on_payout(reference, paid)

        self.db.query(
            "INSERT INTO processed_messages (channel, message_id, processed_at)"
            " VALUES ('bachs', $1, $2) ON CONFLICT DO NOTHING",
            [event_id, Clock.now_iso()],
        )
        return {"ok": True, "duplicate": False}
