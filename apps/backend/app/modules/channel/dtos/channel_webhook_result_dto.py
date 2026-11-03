from __future__ import annotations

from pydantic import BaseModel, Field


class ChannelWebhookResultDto(BaseModel):
    ok: bool = True
    handled: list[str] = Field(
        description="One outcome per message in the delivery: agent | command | "
                    "unlinked | asleep | voice_unheard | duplicate | ignored | error. "
                    "For debugging, not display.",
        examples=[["agent"]],
    )
