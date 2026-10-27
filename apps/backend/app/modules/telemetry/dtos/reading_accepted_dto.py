from __future__ import annotations

from pydantic import BaseModel, Field


class ReadingAcceptedDto(BaseModel):
    accepted: bool = True
    count: int = Field(description="Readings stored for this account.", examples=[42])
