"""Who is logged in — Neon Auth sessions, read from our own database.

Sign-up and sign-in happen in the browser, straight against Neon Auth (see
`packages/api/src/auth.ts`). Neon stores the result in the same Postgres database we
already talk to: a row in `neon_auth.session` with the bearer token the browser was
handed, and a row in `neon_auth.user` with the person's id.

That is the whole reason this file exists. The obvious alternative — verify the JWT
against the published JWKS — does not work in a standard-library backend: Neon signs
with **Ed25519** (`{"crv": "Ed25519", "kty": "OKP"}` as of 2026-10-26) and Python's
stdlib has no Ed25519 verifier. Adding `cryptography` would break the rule that this
backend installs nothing.

Reading the session row is better than a JWT check anyway, because it is a *revocation*
check too: signing out deletes the row, and the token stops working on the next
request rather than whenever it expires.

Two rules:

- **The token is a bearer credential.** It is compared in constant time, never
  logged, and never echoed into an error.
- **A session maps to an app account, not the other way round.** `accounts.id` is
  ours; `accounts.auth_user_id` is Neon's. If the login provider is ever replaced,
  only this file changes.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Any

import neon


@dataclass(frozen=True)
class Identity:
    """A verified login: Neon's user, and where to find them in our tables."""

    auth_user_id: str
    email: str
    name: str | None


def identity_for_token(db: neon.Database, token: str) -> Identity | None:
    """The person behind a bearer token, or None if it is dead, expired or fake."""
    token = (token or "").strip()
    if not token or len(token) > 512:
        return None
    row = db.one(
        'SELECT s."userId" AS auth_user_id, u.email, u.name'
        " FROM neon_auth.session s"
        ' JOIN neon_auth."user" u ON u.id = s."userId"'
        ' WHERE s.token = $1 AND s."expiresAt" > now()'
        "   AND u.banned IS NOT TRUE",
        [token],
    )
    if row is None:
        return None
    return Identity(
        auth_user_id=str(row["auth_user_id"]),
        email=str(row["email"]),
        name=row["name"],
    )


def bearer(header: str | None) -> str | None:
    """Pull the token out of `Authorization: Bearer <token>`."""
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None


def same_token(left: str, right: str) -> bool:
    """Constant-time compare, for anywhere a token is checked by hand."""
    return hmac.compare_digest(left.encode(), right.encode())


def session_account(db: neon.Database, token: str, *, now: str) -> dict[str, Any] | None:
    """Resolve a bearer token to our account row in **one** round trip.

    The obvious shape is two queries — verify the session, then look up or create the
    account — and at ~280 ms per query from Lagos that is a visible half-second on
    every request. This does both in one statement: the session is the `INSERT ...
    SELECT` source, so a dead token inserts no row and returns nothing, and a live one
    either creates the account or refreshes it on the way back.
    """
    token = (token or "").strip()
    if not token or len(token) > 512:
        return None
    return db.one(
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
        [new_account_id(), token, now],
    )


def account_id_for(db: neon.Database, identity: Identity, *, now: str) -> dict[str, Any]:
    """The app account for this login, created on first sight.

    One statement, so two tabs signing in at the same time cannot both decide the
    account is missing and insert it twice: `auth_user_id` is unique, and the
    conflict path returns the winner's row. The email is refreshed on every login so
    a changed address does not linger here.
    """
    row = db.one(
        "INSERT INTO accounts (id, auth_user_id, email, name, created_at)"
        " VALUES ($1, $2, $3, $4, $5)"
        " ON CONFLICT (auth_user_id) DO UPDATE SET email = EXCLUDED.email,"
        " name = EXCLUDED.name"
        " RETURNING id, seeded_at",
        [new_account_id(), identity.auth_user_id, identity.email,
         identity.name, now],
    )
    if row is None:  # pragma: no cover - INSERT ... RETURNING always returns
        raise neon.DatabaseError("could not create an account")
    return row


def new_account_id() -> str:
    import secrets

    return f"acct_{secrets.token_hex(8)}"


def mark_seeded(db: neon.Database, account_id: str, now: str) -> None:
    db.query("UPDATE accounts SET seeded_at = $1 WHERE id = $2", [now, account_id])
