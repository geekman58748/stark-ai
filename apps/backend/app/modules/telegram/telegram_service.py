"""The Telegram door, wired to this server: one bot, speaking for one account.

The bot is the one single-tenant surface left: it acts for exactly the account
named by `STARK_TG_OWNER_EMAIL`, resolved at use rather than at boot (the account
usually does not exist yet when the server starts). It refuses every update until
both Telegram secrets are set (fail closed).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from app.common.api_error import ApiError
from app.database import neon
from app.modules.account.account_service import AccountService
from app.modules.telegram import telegram
from app.modules.telegram.identity_repository import IdentityRepository
from app.modules.turnlog.turn_logger import TurnLogger
from app.modules.voice import stt
from app.shared.services.api_config_service import ApiConfigService


class TelegramService:
    def __init__(self, config: ApiConfigService, db: neon.Database,
                 identities: IdentityRepository, accounts: AccountService) -> None:
        self.config = config
        self.db = db
        self.accounts = accounts
        self._owner_id: Optional[str] = None
        self.adapter = telegram.TelegramAdapter(
            agent=self,
            identities=identities,
            bot_token=config.telegram_bot_token,
            secret=config.telegram_webhook_secret,
            owner_user_id=self.owner_account_id,
            # Voice notes go through the same Whisper the web door uses; OGG is
            # Telegram's own format.
            transcribe=lambda clip: stt.transcribe(clip, mime="audio/ogg"),
            on_turn=self.log_turn,
            log=lambda line: print(f"  [tg] {line}"),
        )

    def owner_account_id(self) -> str:
        """The bot's account, looked up by email. Only a hit is cached, so an owner
        who signs up after boot is found on the next update."""
        if self._owner_id is None and self.config.telegram_owner_email:
            row = self.db.one("SELECT id FROM accounts WHERE lower(email) = $1",
                              [self.config.telegram_owner_email])
            self._owner_id = row["id"] if row else None
        return self._owner_id or ""

    def respond(self, transcript: str, thread: Optional[str] = None) -> Any:
        """The adapter's agent: run the owner's agent, never a web request's."""
        owner = self.owner_account_id()
        if not owner:
            raise RuntimeError("STARK_TG_OWNER_EMAIL does not name an account")
        return self.accounts.state(owner).agent.respond(transcript, thread=thread)

    def link_code(self, account_id: str) -> dict[str, Any]:
        try:
            payload = self.adapter.link_code()
        except telegram.TelegramError as err:
            raise ApiError(err.status, err.code, err.message) from err
        payload["user_id"] = account_id
        return payload

    def webhook(self, raw: bytes, secret_header: Optional[str]) -> dict[str, Any]:
        """Verified before parsing: the secret check runs on exactly what was sent."""
        try:
            self.adapter.verify_secret(secret_header)
        except telegram.TelegramError as err:
            raise ApiError(err.status, err.code, err.message) from err
        try:
            update = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            raise ApiError(400, "bad_update", "Body is not JSON.") from None
        return self.adapter.handle_update(update)

    def log_turn(self, turn: dict) -> None:
        """Write one Telegram exchange to the same log `/v1/voice` writes to, plus
        `channel`, so both doors read back the same way."""
        result = turn.get("result")
        owner = self.owner_account_id()
        TurnLogger.turn(
            agent=self.accounts.state(owner).agent if owner else None,
            outcome=turn.get("outcome") or "answered",
            clip=None, mime=None,
            heard=turn.get("heard") or "",
            said=turn.get("said"),
            payload={
                "reply": getattr(result, "reply", None) or turn.get("reply"),
                "actions": getattr(result, "actions", None),
                "code": getattr(result, "code", None),
                "receipt_id": getattr(result, "receipt_id", None),
                "token": getattr(result, "token", None),
            },
            speak=None,
            conversation=getattr(result, "conversation", None),
            channel=telegram.CHANNEL,
        )
