from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from app.common.dto.contract_field import ContractField


class UpdateLimitsDto(BaseModel):
    """Send either or both. Each must be a positive integer, and per-payment may not
    exceed monthly (`bad_limits`)."""

    monthly_cap_ngn: Optional[int] = Field(default=None, examples=[40000])
    per_payment_cap_ngn: Optional[int] = Field(default=None, examples=[5000])

    @field_validator("monthly_cap_ngn", "per_payment_cap_ngn", mode="before")
    @classmethod
    def cap(cls, value: Any, info: ValidationInfo) -> Optional[int]:
        return ContractField.optional_integer(
            value, "bad_limits", f"{info.field_name} must be an integer"
        )
