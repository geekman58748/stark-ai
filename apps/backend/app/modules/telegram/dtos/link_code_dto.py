from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LinkCodeDto(BaseModel):
    code: str = Field(examples=["491804"])
    channel: str = Field(examples=["telegram"])
    expires_in: int = Field(description="Seconds.", examples=[600])
    bot_username: Optional[str] = Field(examples=["hellostarkai_bot"])
    deep_link: Optional[str] = Field(examples=["https://t.me/hellostarkai_bot?start=491804"])
    user_id: str = Field(examples=["acct_3f9a1c2b4d6e8f0a"])
