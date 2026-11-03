from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ControlsDto(BaseModel):
    paused: bool = Field(description="True while every payment is refused.",
                         examples=[False])
    paused_at: Optional[str] = Field(description="When it was paused; null while active.",
                                     examples=[None])
