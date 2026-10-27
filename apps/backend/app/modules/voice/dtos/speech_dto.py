from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SpeechDto(BaseModel):
    audio: Optional[str] = Field(
        description="A WAV data URL, or null when voice is off (200 either way).",
        examples=["data:audio/wav;base64,UklGR…"],
    )
