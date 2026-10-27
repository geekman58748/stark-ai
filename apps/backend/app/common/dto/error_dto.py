from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDto(BaseModel):
    """Every non-2xx body. Branch on `code`, never on `message`."""

    code: str = Field(examples=["over_cap"])
    message: str = Field(examples=["That would go over your monthly limit."])
    detail: dict[str, Any] = Field(
        default_factory=dict,
        examples=[{"cap_ngn": 30000, "spent_ngn": 23000, "remaining_ngn": 7000}],
    )
