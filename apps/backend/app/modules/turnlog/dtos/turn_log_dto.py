from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TurnLogDto(BaseModel):
    enabled: bool = True
    count: int = Field(examples=[1])
    entries: list[dict[str, Any]] = Field(
        description="One object per turn (`kind: turn`) or synthesis (`kind: speak`).")
