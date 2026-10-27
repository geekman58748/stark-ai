from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.common.dto.contract_field import ContractField


class CreatePaymentDto(BaseModel):
    bill_id: str = Field(default="", examples=["bill_home_meter"])
    amount_ngn: int = Field(
        default=0, examples=[5000],
        description="Integer naira. Data and TV must equal the bill's plan_price_ngn.",
    )

    @field_validator("bill_id", mode="before")
    @classmethod
    def bill(cls, value: Any) -> str:
        return ContractField.text(value)

    @field_validator("amount_ngn", mode="before")
    @classmethod
    def amount(cls, value: Any) -> int:
        return ContractField.integer(value, "bad_amount", "amount_ngn must be an integer")
