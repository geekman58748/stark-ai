"""The SMS door (Twilio Programmable Messaging): verify, identify, answer in TwiML.

The fallback channel of HANDOFF §8A, and the one that reaches an iPhone's
Messages app. Text only, both ways: MMS voice is unreliable, so a message with
media gets the "text and voice notes" sentence like any unreadable kind.

1. **Signature, before acting.** `X-Twilio-Signature` is checked in constant
   time against the auth token, the public URL and the form params. Twilio
   signs the decoded form, not the bytes, so the form is decoded to check it;
   nothing in it is read until the check passes, and an undecodable body is
   refused as unsigned. No `TWILIO_AUTH_TOKEN` → every request is
   refused (`webhook_unconfigured`).
2. Dedupe on `MessageSid`, commands, identity and the agent — `PhoneRouter`.
3. The reply goes back as the webhook's TwiML body, so there is no outbound
   API call and no second credential.
"""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import parse_qs

from app.modules.channel.channel_error import ChannelError
from app.modules.channel.channel_turn import ChannelTurn
from app.modules.channel.inbound_message import InboundMessage
from app.modules.channel.phone_number import PhoneNumber
from app.modules.channel.phone_router import PhoneRouter
from app.modules.control.control_service import ControlService
from app.modules.sms.twilio_signature import TwilioSignature
from app.modules.sms.twiml import Twiml
from app.modules.telegram.identity_repository import IdentityRepository

CHANNEL = "sms"


class SmsAdapter:
    def __init__(
        self,
        *,
        identities: IdentityRepository,
        respond: Callable[[str, str, str], Any],
        controls: ControlService | None = None,
        auth_token: str | None,
        webhook_url: str | None = None,
        on_turn: Callable[[ChannelTurn], None] | None = None,
        log: Callable[[str], None] = lambda line: None,
    ) -> None:
        """`webhook_url` pins the URL Twilio signs; without it the request's own URL is used."""
        self.auth_token = auth_token
        self.webhook_url = webhook_url
        self.on_turn = on_turn
        self.log = log
        self.router = PhoneRouter(CHANNEL, "SMS", identities=identities, respond=respond,
                                  controls=controls, log=log)

    @property
    def enabled(self) -> bool:
        return bool(self.auth_token)

    def verified_params(self, request_url: str, raw: bytes,
                        header_value: str | None) -> dict[str, list[str]]:
        """The form Twilio signed, or ChannelError. An unconfigured door or a
        missing signature is refused before the body is even decoded."""
        if not self.enabled:
            raise ChannelError(401, "webhook_unconfigured",
                               "TWILIO_AUTH_TOKEN is not set; refusing all requests.")
        if not header_value:
            raise ChannelError(401, "webhook_unverified", "Missing X-Twilio-Signature.")
        try:
            params = parse_qs(raw.decode("utf-8"), keep_blank_values=True,
                              strict_parsing=bool(raw))
        except (UnicodeDecodeError, ValueError):
            raise ChannelError(401, "webhook_unverified", "Body is not a signed form.") from None
        url = self.webhook_url or request_url
        if not TwilioSignature.valid(self.auth_token, url, params, header_value):
            raise ChannelError(401, "webhook_unverified", "Bad webhook signature.")
        return params

    def handle(self, params: dict[str, list[str]]) -> str:
        """One inbound SMS → the TwiML that answers it."""
        message_id = self._one(params, "MessageSid")
        sender = PhoneNumber.e164(self._one(params, "From"))
        if not message_id or sender is None:
            return Twiml.message(None)
        has_media = self._one(params, "NumMedia") not in ("", "0")
        turn = self.router.route(InboundMessage(
            channel=CHANNEL,
            channel_user_id=sender,
            message_id=message_id,
            text=None if has_media else self._one(params, "Body"),
            media_id=None,
            display_name=None,
        ))
        if turn.outcome != "duplicate" and self.on_turn is not None:
            try:
                self.on_turn(turn)
            except Exception as err:  # a broken log must not break the reply
                self.log(f"sms turn log failed: {type(err).__name__}")
        return Twiml.message(turn.reply)

    @staticmethod
    def _one(params: dict[str, list[str]], name: str) -> str:
        values = params.get(name)
        return values[0] if values else ""

