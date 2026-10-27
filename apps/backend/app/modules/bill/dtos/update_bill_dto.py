from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.common.dto.contract_field import ContractField


class UpdateBillDto(BaseModel):
    """Every field is optional, and *omitted* is different from *sent empty*:
    `renews_on: ""` or `null` clears the date, leaving it out keeps it.
    `BillService.update` reads `model_fields_set` for that."""

    label: Optional[str] = Field(default=None, examples=["Living room"])
    plan: Optional[str] = Field(default=None, examples=["dstv-yanga"])
    renews_on: Optional[str] = Field(default=None, examples=["2026-11-03"])

    @field_validator("label", "plan", "renews_on", mode="before")
    @classmethod
    def as_text(cls, value: Any) -> str:
        return ContractField.text(value)
