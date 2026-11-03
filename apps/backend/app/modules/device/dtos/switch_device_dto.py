from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SwitchDeviceDto(BaseModel):
    """`{"on": true}` — the only thing a client may say about a device."""

    on: bool


class SwitchedDeviceDto(BaseModel):
    """What the device reported after the flip, not what it was asked to do.

    `confirmed` is true only when a status read followed the command, and
    `status` distinguishes a live screen (`on`) from a live socket with an
    asleep set (`standby`) — which is the sentence the reply has to say out
    loud. `simulated` marks the stub that runs when no plug is configured.
    """

    device_id: str
    label: str
    kind: str
    on: bool
    confirmed: bool
    watts: Optional[float]
    status: str
    simulated: bool
