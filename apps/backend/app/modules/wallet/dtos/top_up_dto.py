from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.common.dto.contract_field import ContractField


class TopUpDto(BaseModel):
    amount_ngn: int = Field(default=0, examples=[20000])
    request_id: Optional[str] = Field(
        default=None, examples=["dep_7f3c1a9b2d4e"],
        description="Send your own: repeating it returns 200 with the original entry "
                    "and does not credit twice.",
    )

    @field_validator("amount_ngn", mode="before")
    @classmethod
    def amount(cls, value: Any) -> int:
        return ContractField.integer(value, "bad_amount", "amount_ngn must be an integer")

    @field_validator("request_id", mode="before")
    @classmethod
    def request(cls, value: Any) -> Optional[str]:
        return ContractField.text(value) or None
