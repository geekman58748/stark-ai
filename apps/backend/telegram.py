"""The Telegram door: verify, identify, gate, answer (M4).

One brain, many doors (HANDOFF §8A). This file is transport and identity only —
every utterance that passes the gates ends in `Agent.respond`, the same call
`/v1/voice` uses, and the policy gate sits inside that agent. Nothing here may
spend money or read state on its own.

Order of checks, and why:

1. **Webhook secret, before parsing.** `X-Telegram-Bot-Api-Secret-Token` is
   compared in constant time against `TELEGRAM_WEBHOOK_SECRET`. No secret is
   configured → the adapter refuses everything (`disabled`), because an open
   webhook is a wallet anyone on the internet can talk to.
2. **Dedupe.** Telegram re-delivers updates; each `update_id` is claimed in
   `processed_messages` before any work, so a retry cannot double-pay.
3. **Identity.** An unlinked chat gets link instructions and nothing else —
   never state, never the agent, never a payment. The only claim that counts is
   a 6-digit code minted by the app (`identities.py`).
4. **Wake gate, for voice only.** A voice note must contain "stark", the same
   rule `/v1/voice` enforces, because a voice note can be recorded by accident.
   A typed message in a DM with the bot is deliberate — no wake word needed.
   That split is deliberate; it is not a second brain, it is a UI courtesy.

Nothing here is live until `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_SECRET`
are set. With no `NEAR_AI_API_KEY`, voice notes are answered with a plain
sentence saying they cannot be heard — never a guessed transcript.
"""

from __future__ import annotations

import hmac
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

import audio
import stt

CHANNEL = "telegram"

TELEGRAM_API = "https://api.telegram.org"

LINK_HELP = (
    "You are not linked to a Stark account yet.\n"
    "Open the Stark app, tap Connect Telegram, and send me the 6-digit code it "
    "shows: link 482913"
)
NOT_LINKED_REPLY = (
    "I do not know this chat yet. Get a 6-digit code from the Stark app and "
    "send: link 000000"
)
VOICE_NO_STT = (
    "I cannot hear voice notes right now — text is working. "
    "Type what you need instead."
)
VOICE_ASLEEP = "I'm here — say 'stark' first, then your question."
HELP_TEXT = (
    "Stark pays your household bills inside your limits.\n"
    "Try: 'hello stark how much is left' or 'hello stark pay 5000 for electricity'.\n"
    "Commands: /whoami, /unlink, /help"
)


class TelegramError(Exception):
    """What the HTTP layer turns into a refusal."""

    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message


class AgentLike(Protocol):
    def respond(self, transcript: str) -> Any: ...


class IdentityLike(Protocol):
    def resolve(self, channel: str, channel_user_id: str) -> str | None: ...
    def issue_code(self, user_id: str) -> str: ...
    def consume_code(self, code: str, channel: str, channel_user_id: str,
                     display_name: str | None = None) -> str | None: ...
    def unlink(self, channel: str, channel_user_id: str) -> bool: ...
    def claim_message(self, channel: str, message_id: str) -> bool: ...


# --- transport (real network; injected in tests) -----------------------------


def download_file(file_id: str, *, bot_token: str,
                  timeout: float = 20.0, max_bytes: int = 5 * 1024 * 1024) -> bytes | None:
    """Fetch a Telegram file, bounded. Returns None on any failure."""
    try:
        with urllib.request.urlopen(
            f"{TELEGRAM_API}/bot{bot_token}/getFile?file_id={file_id}",
            timeout=timeout,
        ) as res:
            info = json.loads(res.read() or b"{}")
        path = (info.get("result") or {}).get("file_path")
        if not path:
            return None
        with urllib.request.urlopen(
            f"{TELEGRAM_API}/file/bot{bot_token}/{path}", timeout=timeout
        ) as res:
            data = res.read(max_bytes + 1)
        return data if len(data) <= max_bytes else None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def send_message(chat_id: int, text: str, *, bot_token: str,
                 timeout: float = 15.0) -> bool:
    """One reply. Never raises — a chat that cannot be reached is not an error."""
    body = json.dumps({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(
        f"{TELEGRAM_API}/bot{bot_token}/sendMessage",
        data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


# --- adapter -----------------------------------------------------------------


@dataclass
class TelegramAdapter:
    agent: AgentLike
    identities: IdentityLike
    bot_token: str | None = None
    secret: str | None = None
    owner_user_id: str = "user_tunde"   # the single user this demo binds to
    download: Callable[[str], bytes | None] | None = None
    transcribe: Callable[[bytes], tuple[str | None, str]] | None = None
    send: Callable[[int, str], bool] | None = None
    log: Callable[[str], None] = lambda line: None
    stats: dict[str, int] = field(default_factory=lambda: {
        "updates": 0, "duplicates": 0, "unlinked": 0, "agent": 0,
        "commands": 0, "voice": 0, "ignored": 0,
    })

    @property
    def enabled(self) -> bool:
        """Both secrets present. Otherwise every update is refused."""
        return bool(self.bot_token and self.secret)

    def verify_secret(self, header_value: str | None) -> None:
        """Raise TelegramError unless the webhook is authenticated."""
        if not self.enabled:
            raise TelegramError(401, "webhook_unconfigured",
                                "Telegram secrets are not set; refusing all updates.")
        if not header_value:
            raise TelegramError(401, "webhook_unverified",
                                "Missing X-Telegram-Bot-Api-Secret-Token.")
        if not hmac.compare_digest(header_value.encode(), self.secret.encode()):
            raise TelegramError(401, "webhook_unverified", "Bad webhook secret.")

    # --- entry point ---------------------------------------------------------

    def handle_update(self, update: dict[str, Any]) -> dict[str, Any]:
        self.stats["updates"] += 1
        update_id = str(update.get("update_id") or "")
        message = update.get("message") or update.get("channel_post") or {}
        message_id = str(message.get("message_id") or update_id or "")

        if update_id or message_id:
            if not self.identities.claim_message(CHANNEL, message_id or update_id):
                self.stats["duplicates"] += 1
                return {"ok": True, "handled": "duplicate", "update_id": update.get("update_id")}

        chat_id = (message.get("chat") or {}).get("id")
        if chat_id is None:
            self.stats["ignored"] += 1
            return {"ok": True, "handled": "ignored", "update_id": update.get("update_id")}

        sender = message.get("from") or {}
        channel_user_id = str(sender.get("id") or chat_id)
        display_name = sender.get("first_name") or sender.get("username")
        text = (message.get("text") or message.get("caption") or "").strip()

        try:
            reply = self._route(message, text, channel_user_id, display_name, chat_id)
        except Exception as err:  # a bad update must not 500 the webhook
            self.log(f"telegram update failed: {err}")
            reply = "Something went wrong handling that. Nothing was charged."

        if reply:
            self._send(chat_id, reply)
        return {"ok": True, "handled": self._last_outcome, "update_id": update.get("update_id")}

    _last_outcome = "ignored"

    def _send(self, chat_id: int, text: str) -> None:
        if self.send is not None:
            self.send(chat_id, text)
        elif self.bot_token:
            send_message(chat_id, text, bot_token=self.bot_token)
        else:
            self.log(f"telegram reply to {chat_id}: {text}")

    # --- routing -------------------------------------------------------------

    def _route(self, message: dict, text: str, channel_user_id: str,
               display_name: str | None, chat_id: int) -> str | None:
        if text.startswith("/"):
            self.stats["commands"] += 1
            self._last_outcome = "command"
            return self._command(text, channel_user_id, display_name)

        user_id = self.identities.resolve(CHANNEL, channel_user_id)
        if user_id is None:
            self.stats["unlinked"] += 1
            self._last_outcome = "unlinked"
            return NOT_LINKED_REPLY

        transcript = None
        if message.get("voice") or message.get("audio"):
            self.stats["voice"] += 1
            transcript = self._transcribe(message)
            if transcript is None:
                self._last_outcome = "voice_unheard"
                return VOICE_NO_STT
            if "stark" not in transcript.lower():
                # Same wake rule as /v1/voice: stay silent, not chatty.
                self.stats["ignored"] += 1
                self._last_outcome = "asleep"
                return VOICE_ASLEEP
        elif text:
            transcript = text
        else:
            self.stats["ignored"] += 1
            self._last_outcome = "ignored"
            return "I can only read text and voice notes for now."

        self.stats["agent"] += 1
        self._last_outcome = "agent"
        self.log(f"telegram user={user_id} transcript={transcript!r}")
        return self.agent.respond(transcript).reply

    def _transcribe(self, message: dict) -> str | None:
        voice = message.get("voice") or message.get("audio") or {}
        file_id = voice.get("file_id")
        if not file_id:
            return None
        fetch = self.download
        if fetch is None:
            if not self.bot_token:
                return None
            fetch = lambda fid: download_file(fid, bot_token=self.bot_token)
        raw = fetch(file_id)
        if not raw:
            return None
        wav, why = audio.transcode(raw)
        if wav is None:
            self.log(f"telegram audio decode failed: {why}")
            return None
        speak = self.transcribe or stt.transcribe
        text, why = speak(wav)
        if text is None:
            self.log(f"telegram stt failed: {why}")
        return text

    def _command(self, text: str, channel_user_id: str, display_name: str | None) -> str:
        parts = text.split()
        verb = parts[0].split("@")[0].lower()

        if verb in ("/start", "/help"):
            return HELP_TEXT

        if verb == "/link":
            if self.identities.resolve(CHANNEL, channel_user_id):
                return "This chat is already linked. /whoami to check, /unlink to remove."
            code = parts[1] if len(parts) > 1 else ""
            if not code:
                return "Send the code from the app like this: link 482913"
            user_id = self.identities.consume_code(code, CHANNEL, channel_user_id, display_name)
            if user_id is None:
                return ("That code did not work. Codes expire after 10 minutes and "
                        "are single-use — get a fresh one in the app.")
            return f"Linked. Ask me for your balance, or say 'hello stark pay 5000 for electricity'."

        if verb == "/whoami":
            user_id = self.identities.resolve(CHANNEL, channel_user_id)
            return f"Linked to {user_id}." if user_id else "Not linked."

        if verb == "/unlink":
            if self.identities.unlink(CHANNEL, channel_user_id):
                return "Unlinked. This chat can no longer see or move money."
            return "This chat was not linked."

        return HELP_TEXT
