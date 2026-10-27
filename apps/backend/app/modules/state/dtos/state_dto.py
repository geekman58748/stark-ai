from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.modules.bill.dtos.bill_dto import BillDto
from app.modules.state.dtos.due_soon_dto import DueSoonDto


class StateDto(BaseModel):
    user_id: str = Field(examples=["acct_3f9a1c2b4d6e8f0a"])
    first_name: str = Field(examples=["Tunde"])
    currency: str = Field(default="NGN")
    balance_ngn: int = Field(examples=[64200])
    cap_ngn: int = Field(examples=[30000])
    spent_ngn: int = Field(examples=[23000])
    remaining_cap_ngn: int = Field(examples=[7000])
    units_left: Optional[float] = Field(
        description="Units delivered minus energy measured; null without data.",
        examples=[11.4],
    )
    days_left: Optional[int] = Field(
        description="Units left over the measured daily pace; null without data.",
        examples=[4],
    )
    bills: list[BillDto]
    due_soon: list[DueSoonDto] = Field(
        description="Renewals inside the 7-day window, soonest first.")
    as_of: str = Field(examples=["2026-10-20T19:33:13Z"])
