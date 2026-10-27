from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class VoiceDto(BaseModel):
    """`application/json`, or `multipart/form-data` with an `audio` file part.
    Audio is checked before `transcript_hint`."""

    audio: Optional[str] = Field(
        default=None, description="Base64 or a data: URL. Max 8 MB.",
    )
    audio_type: Optional[str] = Field(
        default=None, examples=["audio/webm"],
        description="The clip's true MIME; it decides how the clip is decoded.",
    )
    transcript_hint: Optional[str] = Field(
        default=None, examples=["hello stark what's my light bill"],
        description="No audio: for probes and tests only.",
    )
    speak: bool = Field(default=True,
                        description="false skips synthesis; speak later with POST /v1/speak.")
