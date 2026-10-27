"""Who is logged in — Neon Auth sessions, read from our own database.

Sign-up and sign-in happen in the browser, straight against Neon Auth (see
`packages/api/src/auth.ts`). Neon stores the result in the same Postgres database we
already talk to: a row in `neon_auth.session` with the bearer token the browser was
handed, and a row in `neon_auth.user` with the person's id.

Reading the session row is a *revocation* check as well as an identity check:
signing out deletes the row, and the token stops working on the next request rather
than whenever it expires.

Two rules:

- **The token is a bearer credential.** It is never logged and never echoed into an
  error.
- **A session maps to an app account, not the other way round.** `accounts.id` is
  ours; `accounts.auth_user_id` is Neon's. If the login provider is ever replaced,
  only this file changes.
"""

from __future__ import annotations

import secrets
from typing import Any, Optional

from app.database import neon


class AuthService:
    MAX_TOKEN_LENGTH = 512

    def __init__(self, db: neon.Database) -> None:
        self.db = db

    @staticmethod
    def bearer(header: Optional[str]) -> Optional[str]:
        """Pull the token out of `Authorization: Bearer <token>`."""
        if not header:
            return None
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer":
            return None
        return token.strip() or None

    def session_account(self, token: str, *, now: str) -> Optional[dict[str, Any]]:
        """Resolve a bearer token to our account row in **one** round trip.

        The obvious shape is two queries — verify the session, then look up or
        create the account — and at ~280 ms per query from Lagos that is a visible
        half-second on every request. This does both in one statement: the session
        is the `INSERT ... SELECT` source, so a dead token inserts no row and
        returns nothing, and a live one either creates the account or refreshes it.
        """
        token = token.strip()
        if not token or len(token) > self.MAX_TOKEN_LENGTH:
            return None
        return self.db.one(
            "WITH s AS ("
            '  SELECT u.id AS auth_user_id, u.email, u.name'
            "  FROM neon_auth.session s"
            '  JOIN neon_auth."user" u ON u.id = s."userId"'
            '  WHERE s.token = $2 AND s."expiresAt" > now() AND u.banned IS NOT TRUE'
            "), a AS ("
            "  INSERT INTO accounts (id, auth_user_id, email, name, created_at)"
            "  SELECT $1, s.auth_user_id, s.email, s.name, $3 FROM s"
            "  ON CONFLICT (auth_user_id) DO UPDATE SET email = EXCLUDED.email,"
            "    name = EXCLUDED.name"
            "  RETURNING id, seeded_at, email, name"
            ")"
            " SELECT id, seeded_at, email, name FROM a",
            [f"acct_{secrets.token_hex(8)}", token, now],
        )

    def mark_seeded(self, account_id: str, now: str) -> None:
        self.db.query("UPDATE accounts SET seeded_at = $1 WHERE id = $2", [now, account_id])

    def needs_opening(self, account_id: str) -> bool:
        """True for an account row that exists and has never been opened."""
        row = self.db.one("SELECT seeded_at FROM accounts WHERE id = $1", [account_id])
        return row is not None and row["seeded_at"] is None

    def logout(self, token: str) -> None:
        """Deleting the provider's session row is what actually signs a token out."""
        self.db.query("DELETE FROM neon_auth.session WHERE token = $1", [token])
