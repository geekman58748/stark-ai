"""The part of Meta's `messages` webhook the WhatsApp door reads, validated once.

Modelled on Meta's published Cloud API webhook reference (not captured live).
Unknown fields are ignored; a delivery that carries only `statuses` (sent,
delivered, read receipts) validates with no messages and is answered `[]`.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class WhatsAppText(BaseModel):
    body: str


class WhatsAppAudio(BaseModel):
    id: str


class WhatsAppMessage(BaseModel):
    id: str
    sender: str = Field(alias="from")
    type: str
    text: Optional[WhatsAppText] = None
    audio: Optional[WhatsAppAudio] = None


class WhatsAppProfile(BaseModel):
    name: Optional[str] = None


class WhatsAppContact(BaseModel):
    wa_id: str
    profile: Optional[WhatsAppProfile] = None


class WhatsAppValue(BaseModel):
    contacts: list[WhatsAppContact] = []
    messages: list[WhatsAppMessage] = []


class WhatsAppChange(BaseModel):
    field: str
    value: WhatsAppValue


class WhatsAppEntry(BaseModel):
    changes: list[WhatsAppChange] = []


class WhatsAppWebhookDto(BaseModel):
    object: str
    entry: list[WhatsAppEntry] = []
