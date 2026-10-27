from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.common.dto.contract_field import ContractField


class CreateBillDto(BaseModel):
    """Every field arrives as text and is checked by `BillService.add`, which owns the
    codes for each rule (`bad_kind`, `bad_reference`, `plan_required`, …)."""

    kind: str = Field(default="", examples=["data"],
                      description="electricity, airtime, data, tv, internet or water")
    provider: str = Field(default="", examples=["MTN"])
    reference: str = Field(default="", examples=["08031234567"],
                           description="Whitespace is stripped; 4–32 characters.")
    label: str = Field(default="", examples=["My line"],
                       description="Defaults to the provider.")
    plan: str = Field(default="", examples=["mtn-100mb-1000"],
                      description="Required for data and plan-priced TV, from GET /v1/plans.")
    renews_on: str = Field(default="", examples=["2026-11-03"],
                           description="Optional YYYY-MM-DD renewal date.")

    @field_validator("kind", "provider", "reference", "label", "plan", "renews_on",
                     mode="before")
    @classmethod
    def as_text(cls, value: Any) -> str:
        return ContractField.text(value)
