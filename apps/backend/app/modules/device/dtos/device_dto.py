from __future__ import annotations

from pydantic import BaseModel


class DeviceDto(BaseModel):
    """One switchable device. Additive-only, like the rest of the contract."""

    id: str
    label: str
    kind: str
