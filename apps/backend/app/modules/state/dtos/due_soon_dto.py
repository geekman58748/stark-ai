from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DueSoonDto(BaseModel):
    id: str = Field(examples=["bill_dstv"])
    kind: str = Field(examples=["tv"])
    provider: str = Field(examples=["DStv"])
    label: str = Field(examples=["Living room TV"])
    renews_on: str = Field(examples=["2026-10-27"])
    days_until: int = Field(description="Negative when overdue inside the window.",
                            examples=[3])
    price_ngn: Optional[int] = Field(
        description="The plan's price, else the last amount paid, else null.",
        examples=[7900],
    )
