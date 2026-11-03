"""The WhatsApp door (Meta WhatsApp Business Cloud API): verify, identify, answer.

Transport only, like the Telegram door. Every message that passes the gates
ends in the linked account's `Agent.respond`, through `PhoneRouter`, and the
policy gate sits inside that agent.

Order of checks:

1. **Signature, before parsing.** `X-Hub-Signature-256` is `sha256=` + the
   HMAC-SHA256 of the raw body under the Meta app secret, compared in constant
   time. Not configured → every request is refused (`webhook_unconfigured`).
2. **The subscribe handshake** (`GET`): `hub.verify_token` must equal
   `WHATSAPP_VERIFY_TOKEN`; then `hub.challenge` is echoed.
3. Dedupe, commands, identity, wake gate and the agent — `PhoneRouter`.

A voice note is fetched through the Graph API (media id → URL → bytes, bearer
token on both hops), capped at `audio.MAX_INPUT_BYTES` before and during the
download, normalised by `audio.transcode` (which caps duration at
`audio.MAX_SECONDS`) and transcribed by `stt.transcribe`. It is answered with a
voice note when TTS works — upload OGG/Opus, then send it — and with text on
every failure of that path.

Nothing is live until all four `WHATSAPP_*` settings are present.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, Callable

from app.modules.channel.channel_error import ChannelError
from app.modules.channel.channel_turn import ChannelTurn
from app.modules.channel.inbound_message import InboundMessage
from app.modules.channel.phone_number import PhoneNumber
from app.modules.channel.phone_router import PhoneRouter
from app.modules.control.control_service import ControlService
from app.modules.telegram.identity_repository import IdentityRepository
from app.modules.voice import audio
from app.modules.voice import stt
from app.modules.voice import tts
from app.modules.whatsapp.dtos.whatsapp_webhook_dto import WhatsAppMessage, WhatsAppWebhookDto
from app.modules.whatsapp.graph_api import GraphApi

CHANNEL = "whatsapp"


class WhatsAppAdapter:
    def __init__(
        self,
        *,
        identities: IdentityRepository,
        respond: Callable[[str, str, str], Any],
        controls: ControlService | None = None,
        graph: GraphApi | None,
        app_secret: str | None,
        verify_token: str | None,
        transcribe: Callable[[bytes], tuple[str | None, str]] = stt.transcribe,
        speak: Callable[[str], bytes | None] = tts.voice_note,
        on_turn: Callable[[ChannelTurn], None] | None = None,
        log: Callable[[str], None] = lambda line: None,
    ) -> None:
        """`respond(user_id, said, thread)` runs that account's agent. `graph` is
        None until both the access token and the phone number id are set."""
        self.graph = graph
        self.app_secret = app_secret
        self.verify_token = verify_token
        self.transcribe = transcribe
        self.speak = speak
        self.on_turn = on_turn
        self.log = log
        self.router = PhoneRouter(CHANNEL, "WhatsApp", identities=identities,
                                  respond=respond, controls=controls,
                                  hear=self._hear, log=log)

    @property
    def enabled(self) -> bool:
        return bool(self.graph and self.app_secret and self.verify_token)

    def verify_signature(self, raw: bytes, header_value: str | None) -> None:
        """Raise ChannelError unless `raw` is exactly what Meta signed."""
        if not self.enabled:
            raise ChannelError(401, "webhook_unconfigured",
                               "WhatsApp settings are not set; refusing all requests.")
        if not header_value or not header_value.startswith("sha256="):
            raise ChannelError(401, "webhook_unverified", "Missing X-Hub-Signature-256.")
        expected = hmac.new(self.app_secret.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(header_value[len("sha256="):].encode(), expected.encode()):
            raise ChannelError(401, "webhook_unverified", "Bad webhook signature.")

    def verify_handshake(self, mode: str | None, token: str | None,
                         challenge: str | None) -> str:
        """Meta's `GET` subscribe check. Returns the challenge to echo."""
        if not self.enabled:
            raise ChannelError(401, "webhook_unconfigured",
                               "WhatsApp settings are not set; refusing all requests.")
        if mode != "subscribe" or not token or challenge is None:
            raise ChannelError(401, "webhook_unverified", "Not a subscribe handshake.")
        if not hmac.compare_digest(token.encode(), self.verify_token.encode()):
            raise ChannelError(401, "webhook_unverified", "Bad verify token.")
        return challenge

    def handle(self, payload: WhatsAppWebhookDto) -> list[str]:
        """Every message in a delivery, in order. Statuses and other fields are skipped."""
        outcomes: list[str] = []
        for entry in payload.entry:
            for change in entry.changes:
                if change.field != "messages":
                    continue
                names = {c.wa_id: c.profile.name for c in change.value.contacts if c.profile}
                for message in change.value.messages:
                    outcomes.append(self._handle_message(message, names.get(message.sender)))
        return outcomes

    def _handle_message(self, message: WhatsAppMessage, display_name: str | None) -> str:
        sender = PhoneNumber.e164(message.sender)
        if sender is None:
            return "ignored"
        turn = self.router.route(InboundMessage(
            channel=CHANNEL,
            channel_user_id=sender,
            message_id=message.id,
            text=message.text.body if message.type == "text" and message.text else None,
            media_id=message.audio.id if message.type == "audio" and message.audio else None,
            display_name=display_name,
        ))
        if turn.reply:
            self._deliver(sender, turn.reply, spoken=turn.spoken)
        if turn.outcome != "duplicate" and self.on_turn is not None:
            try:
                self.on_turn(turn)
            except Exception as err:  # a broken log must not break the reply
                self.log(f"whatsapp turn log failed: {type(err).__name__}")
        return turn.outcome

    def _deliver(self, to: str, text: str, *, spoken: bool) -> None:
        """A voice note when a voice note reached the agent and TTS works; text otherwise."""
        if spoken:
            ogg = self.speak(text)
            media_id = self.graph.upload_audio(ogg) if ogg else None
            if media_id and self.graph.send_audio(to, media_id):
                return
        if not self.graph.send_text(to, text):
            self.log(f"whatsapp reply to {PhoneNumber.redact(to)} failed")

    def _hear(self, media_id: str) -> str | None:
        raw = self.graph.media(media_id, max_bytes=audio.MAX_INPUT_BYTES)
        if raw is None:
            self.log("whatsapp media download failed")
            return None
        wav, why = audio.transcode(raw, filename="voice.ogg")
        if wav is None:
            self.log(f"whatsapp audio decode failed: {why}")
            return None
        text, why = self.transcribe(wav)
        if text is None:
            self.log(f"whatsapp stt failed: {why}")
        return text
