"""Pure policy rules for Stark — the Python mirror of `contracts/vault/src/policy.rs`.

Why this file exists: the vault enforces the caps onchain, but a payment that the
vault will reject must never reach the point of being signed and sent. The agent
runs *these* rules first, so the user hears a plain-English refusal instead of a
failed transaction. Same order, same codes, same sentences as the contract.

If you change a rule, change it in both places. `test_agent.py` reads the Rust
source and fails if a code or message drifts.

Zero dependencies. Integer naira only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

# Stable machine codes. The frontend and the agent branch on these, never on the
# human sentence. These strings are identical to `Rejection::code()` in Rust.
BAD_AMOUNT = "bad_amount"
OVER_PER_PAYMENT_CAP = "over_per_payment_cap"
OVER_CAP = "over_cap"
METER_NOT_ALLOWED = "meter_not_allowed"
INSUFFICIENT_BALANCE = "insufficient_balance"

ALL_CODES = (
    BAD_AMOUNT,
    OVER_PER_PAYMENT_CAP,
    OVER_CAP,
    METER_NOT_ALLOWED,
    INSUFFICIENT_BALANCE,
)

# Plain English only. No "vault", no "USDC", no addresses — these lines are
# spoken out loud by TTS. Identical to `Rejection::as_str()` in Rust.
MESSAGES = {
    BAD_AMOUNT: "That amount needs to be above zero.",
    OVER_PER_PAYMENT_CAP: "That's over the most you allow in one go.",
    OVER_CAP: "That would go over your monthly limit.",
    METER_NOT_ALLOWED: "That meter isn't on your list. Add it first, or pick another one.",
    INSUFFICIENT_BALANCE: "There isn't enough in your balance for that.",
}


@dataclass(frozen=True)
class Rejection:
    """Why a payment was refused. `code` is for code, `message` is for people."""

    code: str
    detail: dict[str, int] = field(default_factory=dict)

    @property
    def message(self) -> str:
        return MESSAGES[self.code]

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "detail": dict(self.detail)}


def check_payment(
    monthly_cap_ngn: int,
    per_payment_cap_ngn: int,
    spent_this_period_ngn: int,
    balance_ngn: int,
    amount_ngn: int,
    meter_allowed: bool,
) -> Rejection | None:
    """Decide whether a payment is allowed. Returns `None` when it is.

    The order is deliberate and mirrors the Rust contract exactly:

    1. per-payment cap  — cheapest, most specific refusal
    2. monthly cap      — the headline safety guarantee
    3. allowlist        — never pay a meter the owner didn't name
    4. balance          — checked last, so a policy problem reads as policy, not money

    A spend that overflows is treated as over the cap rather than clamped, which
    is what the Rust side does with `checked_add`.
    """
    if amount_ngn == 0:
        return Rejection(BAD_AMOUNT)
    if amount_ngn > per_payment_cap_ngn:
        return Rejection(
            OVER_PER_PAYMENT_CAP,
            {"amount_ngn": amount_ngn, "cap_ngn": per_payment_cap_ngn},
        )
    if spent_this_period_ngn + amount_ngn > monthly_cap_ngn:
        return Rejection(
            OVER_CAP,
            {
                "cap_ngn": monthly_cap_ngn,
                "spent_ngn": spent_this_period_ngn,
                "remaining_ngn": remaining_cap(monthly_cap_ngn, spent_this_period_ngn),
            },
        )
    if not meter_allowed:
        return Rejection(METER_NOT_ALLOWED)
    if amount_ngn > balance_ngn:
        return Rejection(
            INSUFFICIENT_BALANCE,
            {"need_ngn": amount_ngn, "have_ngn": balance_ngn},
        )
    return None


def remaining_cap(monthly_cap_ngn: int, spent_this_period_ngn: int) -> int:
    """Remaining allowance for the current period. Never negative."""
    return max(monthly_cap_ngn - spent_this_period_ngn, 0)


def period_key(timestamp_nanos: int) -> str:
    """`"YYYY-MM"` for a block timestamp. This is what makes the cap *monthly*.

    The Rust side derives this with integer civil-calendar math; `datetime` in UTC
    agrees for every timestamp the contract can see in practice (post-1970).
    """
    seconds = timestamp_nanos // 1_000_000_000
    dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return f"{dt.year:04d}-{dt.month:02d}"


def now_period_key() -> str:
    """The calendar month the current clock is in."""
    return datetime.now(timezone.utc).strftime("%Y-%m")
