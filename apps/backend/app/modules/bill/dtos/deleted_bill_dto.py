from __future__ import annotations

from pydantic import BaseModel, Field


class DeletedBillDto(BaseModel):
    deleted: bool = True
    bill_id: str = Field(examples=["bill_abc123"])
