from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class WebhookResultDto(BaseModel):
    ok: bool = True
    handled: str = Field(
        description="agent | command | unlinked | asleep | voice_unheard | duplicate | "
                    "ignored. For debugging, not display.",
        examples=["agent"],
    )
    update_id: Optional[int] = Field(default=None, examples=[918273645])
