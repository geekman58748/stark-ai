from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChannelTurn:
    """What one inbound message came to, for the adapter to deliver and log.

    `outcome` is one of: agent | command | unlinked | asleep | voice_unheard |
    duplicate | ignored | error. `reply` is None only for a duplicate, which is
    answered by the first delivery. `spoken` asks the adapter for a voice reply:
    true only when a voice note reached the agent.
    """

    outcome: str
    reply: str | None
    spoken: bool = False
    user_id: str | None = None
    heard: str | None = None
    said: str | None = None
    result: Any = None
