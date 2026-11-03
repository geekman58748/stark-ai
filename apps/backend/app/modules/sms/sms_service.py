"""The SMS door, wired to this server: any linked number, speaking for its own account.

Same scoping as WhatsApp: a number speaks for the account that minted its link
code. It refuses every request until `TWILIO_AUTH_TOKEN` is set (fail closed).
"""

from __future__ import annotations

from typing import Any, Optional

from app.common.api_error import ApiError
from app.modules.account.account_service import AccountService
from app.modules.channel.channel_error import ChannelError
from app.modules.channel.channel_turn_log import ChannelTurnLog
from app.modules.control.control_service import ControlService
from app.modules.sms import sms
from app.modules.sms.sms_config import SmsConfig
from app.modules.telegram.identity_repository import CODE_TTL_SECONDS, IdentityRepository


class SmsService:
    def __init__(self, config: SmsConfig, identities: IdentityRepository,
                 accounts: AccountService, controls: ControlService) -> None:
        self.identities = identities
        self.accounts = accounts
        self.adapter = sms.SmsAdapter(
            identities=identities,
            respond=self.respond,
            controls=controls,
            auth_token=config.auth_token,
            webhook_url=config.webhook_url,
            on_turn=ChannelTurnLog(accounts, sms.CHANNEL).write,
            log=lambda line: print(f"  [sms] {line}"),
        )

    def respond(self, user_id: str, said: str, thread: str) -> Any:
        """The linked account's agent — the same `Agent.respond` every door uses."""
        return self.accounts.state(user_id).agent.respond(said, thread=thread)

    def link_code(self, account_id: str) -> dict[str, Any]:
        if not self.adapter.enabled:
            raise ApiError(409, "not_configured", "SMS is not set up on this server.")
        return {
            "code": self.identities.issue_code(account_id),
            "channel": sms.CHANNEL,
            "expires_in": CODE_TTL_SECONDS,
            "user_id": account_id,
        }

    def webhook(self, request_url: str, raw: bytes, signature: Optional[str]) -> str:
        try:
            params = self.adapter.verified_params(request_url, raw, signature)
        except ChannelError as err:
            raise ApiError(err.status, err.code, err.message) from err
        return self.adapter.handle(params)
