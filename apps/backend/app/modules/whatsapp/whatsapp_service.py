"""The WhatsApp door, wired to this server: any linked number, speaking for its own account.

Unlike the Telegram bot (one owner account), a WhatsApp number speaks for the
account that minted its link code, so every read and payment is scoped to the
`user_id` the identity resolves to (HANDOFF §8A). It refuses every request until
all four `WHATSAPP_*` settings are present (fail closed).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import ValidationError

from app.common.api_error import ApiError
from app.modules.account.account_service import AccountService
from app.modules.channel.channel_error import ChannelError
from app.modules.channel.channel_turn_log import ChannelTurnLog
from app.modules.control.control_service import ControlService
from app.modules.telegram.identity_repository import CODE_TTL_SECONDS, IdentityRepository
from app.modules.whatsapp import whatsapp
from app.modules.whatsapp.dtos.whatsapp_webhook_dto import WhatsAppWebhookDto
from app.modules.whatsapp.graph_api import GraphApi
from app.modules.whatsapp.whatsapp_config import WhatsAppConfig


class WhatsAppService:
    def __init__(self, config: WhatsAppConfig, identities: IdentityRepository,
                 accounts: AccountService, controls: ControlService) -> None:
        self.identities = identities
        self.accounts = accounts
        graph = (GraphApi(config.access_token, config.phone_number_id)
                 if config.access_token and config.phone_number_id else None)
        self.adapter = whatsapp.WhatsAppAdapter(
            identities=identities,
            respond=self.respond,
            controls=controls,
            graph=graph,
            app_secret=config.app_secret,
            verify_token=config.verify_token,
            on_turn=ChannelTurnLog(accounts, whatsapp.CHANNEL).write,
            log=lambda line: print(f"  [wa] {line}"),
        )

    def respond(self, user_id: str, said: str, thread: str) -> Any:
        """The linked account's agent — the same `Agent.respond` every door uses."""
        return self.accounts.state(user_id).agent.respond(said, thread=thread)

    def link_code(self, account_id: str) -> dict[str, Any]:
        if not self.adapter.enabled:
            raise ApiError(409, "not_configured", "WhatsApp is not set up on this server.")
        return {
            "code": self.identities.issue_code(account_id),
            "channel": whatsapp.CHANNEL,
            "expires_in": CODE_TTL_SECONDS,
            "user_id": account_id,
        }

    def handshake(self, mode: Optional[str], token: Optional[str],
                  challenge: Optional[str]) -> str:
        try:
            return self.adapter.verify_handshake(mode, token, challenge)
        except ChannelError as err:
            raise ApiError(err.status, err.code, err.message) from err

    def webhook(self, raw: bytes, signature: Optional[str]) -> dict[str, Any]:
        """Verified before parsing: the HMAC runs on exactly the bytes Meta sent."""
        try:
            self.adapter.verify_signature(raw, signature)
        except ChannelError as err:
            raise ApiError(err.status, err.code, err.message) from err
        try:
            payload = WhatsAppWebhookDto.model_validate_json(raw)
        except ValidationError:
            raise ApiError(400, "bad_update", "Body is not a WhatsApp webhook.") from None
        return {"ok": True, "handled": self.adapter.handle(payload)}
