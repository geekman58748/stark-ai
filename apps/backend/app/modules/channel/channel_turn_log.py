from __future__ import annotations

from app.modules.account.account_service import AccountService
from app.modules.channel.channel_turn import ChannelTurn
from app.modules.turnlog.turn_logger import TurnLogger


class ChannelTurnLog:
    """Writes a phone door's exchange to the log `/v1/voice` and Telegram write to,
    tagged with its `channel`, so every door reads back the same way."""

    def __init__(self, accounts: AccountService, channel: str) -> None:
        self.accounts = accounts
        self.channel = channel

    def write(self, turn: ChannelTurn) -> None:
        result = turn.result
        TurnLogger.turn(
            agent=self.accounts.state(turn.user_id).agent if turn.user_id else None,
            outcome=turn.outcome,
            clip=None, mime=None,
            heard=turn.heard or "",
            said=turn.said,
            payload={
                "reply": turn.reply,
                "actions": getattr(result, "actions", None),
                "code": getattr(result, "code", None),
                "receipt_id": getattr(result, "receipt_id", None),
                "token": getattr(result, "token", None),
            },
            speak=None,
            conversation=getattr(result, "conversation", None),
            channel=self.channel,
        )
