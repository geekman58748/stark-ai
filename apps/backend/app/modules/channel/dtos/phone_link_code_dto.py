from __future__ import annotations

from pydantic import BaseModel, Field


class PhoneLinkCodeDto(BaseModel):
    code: str = Field(examples=["491804"])
    channel: str = Field(examples=["whatsapp"])
    expires_in: int = Field(description="Seconds.", examples=[600])
    user_id: str = Field(examples=["acct_3f9a1c2b4d6e8f0a"])
