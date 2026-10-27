"""The contract's error codes, as OpenAPI responses a route can list."""

from __future__ import annotations

from typing import Any

from app.common.dto.error_dto import ErrorDto


class ApiResponses:
    STATUS = {
        "unauthorized": 401,
        "unknown_bill": 404,
        "no_route": 404,
        "bad_amount": 400,
        "bad_watts": 400,
        "bad_kind": 400,
        "bad_reference": 400,
        "bad_bill": 400,
        "bad_renews_on": 400,
        "bad_audio": 400,
        "bad_text": 400,
        "bad_limits": 400,
        "bad_update": 400,
        "unsupported_product": 400,
        "plan_required": 400,
        "unknown_plan": 400,
        "audio_too_large": 413,
        "over_per_payment_cap": 409,
        "over_cap": 409,
        "insufficient_balance": 409,
        "duplicate_bill": 409,
        "bill_in_flight": 409,
        "not_configured": 409,
        "webhook_unconfigured": 401,
        "webhook_unverified": 401,
        "not_available": 501,
        "vendor_failed": 502,
        "no_voice": 503,
        "turnlog_off": 404,
    }

    @staticmethod
    def errors(*codes: str) -> dict[int | str, dict[str, Any]]:
        by_status: dict[int, list[str]] = {}
        for code in codes:
            by_status.setdefault(ApiResponses.STATUS[code], []).append(code)
        return {
            status: {"model": ErrorDto, "description": ", ".join(f"`{c}`" for c in listed)}
            for status, listed in sorted(by_status.items())
        }
