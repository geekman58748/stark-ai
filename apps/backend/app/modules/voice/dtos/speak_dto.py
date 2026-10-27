from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.common.dto.contract_field import ContractField


class SpeakDto(BaseModel):
    text: str = Field(default="", examples=["You've got ₦64,200 in your wallet."],
                      description="Keep it within ~2000 characters.")

    @field_validator("text", mode="before")
    @classmethod
    def as_text(cls, value: Any) -> str:
        return ContractField.text(value)
