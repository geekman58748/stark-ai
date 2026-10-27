from __future__ import annotations

from pydantic import BaseModel, Field


class WalletDto(BaseModel):
    currency: str = Field(default="NGN")
    balance_ngn: int = Field(examples=[64200])
    spent_ngn: int = Field(examples=[23000])
    monthly_cap_ngn: int = Field(examples=[30000])
    remaining_cap_ngn: int = Field(examples=[7000])
    added_this_month_ngn: int = Field(examples=[20000])
