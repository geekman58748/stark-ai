"""Who is talking to us — channel identity linking and webhook dedupe.

The rules this file exists to enforce (HANDOFF §8A):

- **An unknown sender never creates a wallet and never pays.** A Telegram chat that
  has not been linked gets link instructions and nothing else — the agent is never
  called for it.
- **Linking is the only way a channel can claim an account.** A `user_id` in a
  message or a webhook body is never trusted; the only claim that counts is a
  6-digit code issued by the app and redeemed here.
- **One identity maps to exactly one user**; one user may have many identities.
- **Link attempts are rate-limited** and codes expire, are single-use, and are
  stored hashed.

Phone channels normalise to E.164 before calling into this module; Telegram keys
on the numeric chat/user id. Nothing here keys on a display name.

The tables live in the same SQLite file as the receipts (`stark.db`) — same
database for the demo, split later if there is ever more than one user.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_DB = Path(__file__).parent / "stark.db"

CODE_TTL_SECONDS = 600        # 10 minutes, per the handoff design.
MAX_LINK_ATTEMPTS = 5         # per identity per window.
ATTEMPT_WINDOW_SECONDS = 600  # sliding window on failed link attempts.

SCHEMA = """
CREATE TABLE IF NOT EXISTS channel_identities (
    channel        TEXT NOT NULL,
    channel_user_id TEXT NOT NULL,
    user_id        TEXT NOT NULL,
    display_name   TEXT,
    linked_at      TEXT NOT NULL,
    last_seen_at   TEXT,
    PRIMARY KEY (channel, channel_user_id)
);

CREATE TABLE IF NOT EXISTS link_codes (
    code_hash  TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at    TEXT
);

CREATE TABLE IF NOT EXISTS link_attempts (
    channel        TEXT NOT NULL,
    channel_user_id TEXT NOT NULL,
    attempts       INTEGER NOT NULL,
    window_start   TEXT NOT NULL,
    PRIMARY KEY (channel, channel_user_id)
);

CREATE TABLE IF NOT EXISTS processed_messages (
    channel      TEXT NOT NULL,
    message_id   TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    PRIMARY KEY (channel, message_id)
);
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash(code: str) -> str:
    # Unkeyed hash is fine here: the code is 6 random digits, short-lived and
    # rate-limited. A leak of the table is not a leak of a usable identity.
    return hashlib.sha256(code.encode()).hexdigest()


class IdentityStore:
    def __init__(self, path: str | Path = DEFAULT_DB):
        self.path = str(path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.executescript(SCHEMA)

    # --- link codes ----------------------------------------------------------

    def issue_code(self, user_id: str, ttl_seconds: int = CODE_TTL_SECONDS) -> str:
        """Mint a single-use code for `user_id`. Returns the plaintext once."""
        code = f"{secrets.randbelow(1_000_000):06d}"
        now = _now()
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM link_codes WHERE expires_at < ?", (_iso(now),))
            self._conn.execute(
                "INSERT INTO link_codes (code_hash, user_id, created_at, expires_at)"
                " VALUES (?, ?, ?, ?)",
                (_hash(code), user_id, _iso(now),
                 _iso(now + timedelta(seconds=ttl_seconds))),
            )
        return code

    def consume_code(self, code: str, channel: str, channel_user_id: str,
                     display_name: str | None = None) -> str | None:
        """Redeem a code: binds the identity to its user and returns the user_id.

        Fails (returns None) when the code is unknown, expired, already used, or
        the sender has burned through its attempt budget.
        """
        code = (code or "").strip()
        if not code:
            return None
        now = _now()
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT user_id, expires_at, used_at FROM link_codes WHERE code_hash = ?",
                (_hash(code),),
            ).fetchone()
            if row is None or row["used_at"] or row["expires_at"] < _iso(now):
                self._record_failed_attempt_locked(channel, channel_user_id, now)
                return None
            if self._attempts_locked(channel, channel_user_id, now) >= MAX_LINK_ATTEMPTS:
                return None
            self._conn.execute(
                "UPDATE link_codes SET used_at = ? WHERE code_hash = ?",
                (_iso(now), _hash(code)),
            )
            self._conn.execute("DELETE FROM link_attempts WHERE channel = ? AND channel_user_id = ?",
                               (channel, channel_user_id))
            self._conn.execute(
                "INSERT INTO channel_identities"
                " (channel, channel_user_id, user_id, display_name, linked_at, last_seen_at)"
                " VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(channel, channel_user_id) DO UPDATE SET"
                "  user_id = excluded.user_id, display_name = excluded.display_name,"
                "  last_seen_at = excluded.last_seen_at",
                (channel, channel_user_id, row["user_id"], display_name, _iso(now), _iso(now)),
            )
            return str(row["user_id"])

    def _attempts_locked(self, channel: str, channel_user_id: str, now: datetime) -> int:
        row = self._conn.execute(
            "SELECT attempts, window_start FROM link_attempts WHERE channel = ? AND channel_user_id = ?",
            (channel, channel_user_id),
        ).fetchone()
        if row is None:
            return 0
        if row["window_start"] < _iso(now - timedelta(seconds=ATTEMPT_WINDOW_SECONDS)):
            self._conn.execute("DELETE FROM link_attempts WHERE channel = ? AND channel_user_id = ?",
                               (channel, channel_user_id))
            return 0
        return int(row["attempts"])

    def _record_failed_attempt_locked(self, channel: str, channel_user_id: str,
                                      now: datetime) -> None:
        """Count a failed link attempt against this sender, inside its window."""
        attempts = self._attempts_locked(channel, channel_user_id, now)
        window_start = self._window_start_locked(channel, channel_user_id)
        if window_start is None:
            window_start = _iso(now)
        self._conn.execute(
            "INSERT INTO link_attempts (channel, channel_user_id, attempts, window_start)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(channel, channel_user_id) DO UPDATE SET"
            "  attempts = link_attempts.attempts + 1, window_start = excluded.window_start",
            (channel, channel_user_id, attempts + 1, window_start),
        )

    def _window_start_locked(self, channel: str, channel_user_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT window_start FROM link_attempts WHERE channel = ? AND channel_user_id = ?",
            (channel, channel_user_id),
        ).fetchone()
        return row["window_start"] if row else None

    # --- identity ------------------------------------------------------------

    def resolve(self, channel: str, channel_user_id: str) -> str | None:
        """The user this channel identity is bound to, or None."""
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT user_id FROM channel_identities WHERE channel = ? AND channel_user_id = ?",
                (channel, channel_user_id),
            ).fetchone()
            if row:
                self._conn.execute(
                    "UPDATE channel_identities SET last_seen_at = ?"
                    " WHERE channel = ? AND channel_user_id = ?",
                    (_iso(_now()), channel, channel_user_id),
                )
                return str(row["user_id"])
            return None

    def is_linked(self, channel: str, channel_user_id: str) -> bool:
        return self.resolve(channel, channel_user_id) is not None

    def unlink(self, channel: str, channel_user_id: str) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "DELETE FROM channel_identities WHERE channel = ? AND channel_user_id = ?",
                (channel, channel_user_id),
            )
            return cur.rowcount > 0

    def identities_for(self, user_id: str) -> list[dict]:
        with self._lock, self._conn:
            rows = self._conn.execute(
                "SELECT channel, channel_user_id, display_name, linked_at"
                " FROM channel_identities WHERE user_id = ? ORDER BY linked_at",
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def clear(self) -> None:
        """Wipe identities, codes, attempts and dedupe — for `_stub/reset` only."""
        with self._lock, self._conn:
            for table in ("channel_identities", "link_codes", "link_attempts",
                          "processed_messages"):
                self._conn.execute(f"DELETE FROM {table}")

    # --- dedupe --------------------------------------------------------------

    def claim_message(self, channel: str, message_id: str) -> bool:
        """True when this message has not been processed before.

        Telegram re-delivers updates; processing one twice would double-pay or
        double-reply, so every adapter call claims the id first.
        """
        with self._lock, self._conn:
            try:
                self._conn.execute(
                    "INSERT INTO processed_messages (channel, message_id, processed_at)"
                    " VALUES (?, ?, ?)",
                    (channel, message_id, _iso(_now())),
                )
                return True
            except sqlite3.IntegrityError:
                return False
