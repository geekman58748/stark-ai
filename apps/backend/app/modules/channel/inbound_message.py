from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InboundMessage:
    """The adapter contract of HANDOFF §8A, after a webhook has been verified.

    `channel_user_id` is E.164 for phone channels. `media_id` is a voice note the
    adapter still has to download; `text` and `media_id` may both be None for a
    message kind Stark does not read (a sticker, an image).
    """

    channel: str
    channel_user_id: str
    message_id: str
    text: str | None
    media_id: str | None
    display_name: str | None
