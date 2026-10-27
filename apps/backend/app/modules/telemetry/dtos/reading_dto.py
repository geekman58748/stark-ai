from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.common.dto.contract_field import ContractField


class ReadingDto(BaseModel):
    """One sample from a plug or meter sensor. A `ts` is not accepted: readings are
    stamped with the server's clock when they arrive."""

    device_id: str = Field(default="unknown", examples=["ac-plug-1"])
    watts: float = Field(default=0, examples=[1480], description="0 or more.")

    @field_validator("device_id", mode="before")
    @classmethod
    def device(cls, value: Any) -> str:
        return ContractField.text(value) or "unknown"

    @field_validator("watts", mode="before")
    @classmethod
    def power(cls, value: Any) -> float:
        return ContractField.number(value, "bad_watts", "watts must be a number")
