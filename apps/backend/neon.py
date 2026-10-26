"""Postgres, without a Postgres driver.

Neon serves SQL over HTTPS: POST `https://<project-host>/sql` with the connection
string in a header and `{"query", "params"}` in the body. That endpoint speaks the
wire protocol on our behalf, so this module keeps the backend's oldest promise —
**standard library only** — while moving the data off `stark.db` and onto a real
database that survives a laptop closing.

What that costs, measured from Lagos to `us-east-2` on 2026-10-26:

    first query (TLS handshake)   883 ms
    each query after that         260-310 ms

The latency is the ocean, not the protocol: 240 ms of it is one round trip. So the
HTTP connection is kept alive per thread (a fresh TLS handshake per query would
triple every number above) and anything that reads several things at once is
written as **one** statement with CTEs, not four round trips.

The other consequence worth knowing before you write SQL here: the endpoint refuses
multi-statement strings (`cannot insert multiple commands into a prepared
statement`), and it gives you no transaction to open. Any write that must be all-or-
nothing has to be a single statement that does all of it — an `UPDATE ... RETURNING`
feeding an `INSERT ... SELECT`, or a `WITH` around both. `receipts.py` shows the
shape. Do not write two statements and assume the first one stuck.

Timestamps are stored as ISO-8601 UTC **text**, not `timestamptz`, on purpose: the
API has always returned strings, every comparison in the stores is lexicographic
and UTC, and a round trip through `datetime` would only add a place to lose the
timezone. Money stays integer naira in `BIGINT`, same rule as everywhere else.
"""

from __future__ import annotations

import http.client
import json
import os
import ssl
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import unquote, urlparse


class DatabaseError(RuntimeError):
    """A query failed. Carries the SQLSTATE when Postgres gave us one."""

    def __init__(self, message: str, code: str | None = None, *, query: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.query = query


@dataclass(frozen=True)
class Target:
    """Where the database is, parsed once from the connection string."""

    url: str          # the whole DSN, sent to Neon as-is
    host: str         # the pooled host the HTTPS endpoint lives on
    database: str
    user: str

    @classmethod
    def parse(cls, dsn: str) -> "Target":
        parsed = urlparse(dsn)
        if parsed.scheme not in ("postgres", "postgresql"):
            raise DatabaseError(f"not a postgres url: {parsed.scheme or '(none)'}")
        if not parsed.hostname:
            raise DatabaseError("connection string has no host")
        return cls(
            url=dsn,
            host=parsed.hostname,
            database=unquote((parsed.path or "/").lstrip("/") or "postgres"),
            user=unquote(parsed.username or ""),
        )


def target_from_env(name: str = "DATABASE_URL") -> Target | None:
    dsn = (os.environ.get(name) or "").strip()
    if not dsn:
        dsn = (read_env_value(name) or "").strip()
        if dsn:
            os.environ[name] = dsn
    return Target.parse(dsn) if dsn else None


def read_env_value(key: str, path: Path | None = None) -> str | None:
    """One key from `apps/backend/.env`, for when the shell did not source it.

    `bun dev` sources the file; the unit tests and a bare `python3 server.py` do not,
    and a missing database url in a test run reads as fifty unrelated import errors.

    Deliberately **one key**, named by the caller. Loading the whole file would drag
    `NEAR_AI_API_KEY` and the VTpass credentials into tests that assert what happens
    when they are absent — which is exactly the bug this docstring replaced.
    """
    env_path = path or Path(__file__).parent / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() == key:
            return value.strip().strip("'\"") or None
    return None


class _Wire:
    """One HTTPS connection, and the lock that lets a thread use it exclusively."""

    def __init__(self, host: str, timeout: float) -> None:
        self.conn = http.client.HTTPSConnection(
            host, timeout=timeout, context=ssl.create_default_context()
        )
        self.lock = threading.Lock()


class Database:
    """A small pool of keep-alive HTTPS connections, and the queries on them.

    The connection matters more than it looks. A TLS handshake to `us-east-2` costs
    ~880 ms from Lagos and a query on an already-open connection ~280 ms, so a pool
    is the difference between every request paying the handshake and only the first
    one doing so.

    A per-thread connection would not help: `ThreadingHTTPServer` starts a new
    thread for every request, and thread-local storage would mean a handshake per
    request. So connections are borrowed from a pool and returned, one thread at a
    time each, which also keeps concurrent readers from serialising behind one
    another.
    """

    MAX_IDLE = 8

    def __init__(self, target: Target, *, timeout: float = 30.0) -> None:
        self.target = target
        self.timeout = timeout
        self._idle: list[_Wire] = []
        self._mutex = threading.Lock()

    # --- connection ----------------------------------------------------------

    def _acquire(self) -> _Wire:
        with self._mutex:
            if self._idle:
                return self._idle.pop()
        return _Wire(self.target.host, self.timeout)

    def _release(self, wire: _Wire) -> None:
        with self._mutex:
            if len(self._idle) < self.MAX_IDLE:
                self._idle.append(wire)
                return
        self._close(wire)

    @staticmethod
    def _close(wire: _Wire) -> None:
        try:
            wire.conn.close()
        except Exception:
            pass

    # --- query ---------------------------------------------------------------

    def query(self, sql: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
        """Run one statement. Returns rows as dicts (empty for a write)."""
        started = time.perf_counter()
        body = json.dumps({"query": sql, "params": list(params or [])})
        headers = {
            "Neon-Connection-String": self.target.url,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        last: Exception | None = None
        wire: _Wire | None = None
        for attempt in (0, 1):
            try:
                if wire is None:
                    wire = self._acquire()
                with wire.lock:
                    wire.conn.request("POST", "/sql", body, headers)
                    response = wire.conn.getresponse()
                    raw = response.read()
                self._release(wire)
                wire = None
                break
            except (http.client.HTTPException, OSError) as err:
                # A pooled connection can be reaped while it sits idle. One retry
                # on a fresh connection is the whole fix; a second failure is real.
                last = err
                if wire is not None:
                    self._close(wire)
                    wire = None
                if attempt:
                    raise DatabaseError(f"database unreachable: {err}") from err
                time.sleep(0.05)
        else:  # pragma: no cover - the loop always breaks or raises
            raise DatabaseError(f"database unreachable: {last}")

        if os.environ.get("STARK_DB_TRACE"):
            print(f"  [db] {round((time.perf_counter() - started) * 1000)}ms "
                  f"{sql.strip().splitlines()[0][:70]}")
        if response.status >= 400:
            raise DatabaseError(_error_message(raw, response.status), _error_code(raw),
                                query=sql)
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError as err:
            raise DatabaseError(f"database returned non-json: {raw[:200]!r}") from err
        rows = payload.get("rows") or []
        return [dict(row) for row in rows]

    def one(self, sql: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def value(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        row = self.one(sql, params)
        if row is None:
            return None
        return next(iter(row.values()))

    def health(self) -> dict[str, Any]:
        row = self.one("SELECT current_database() AS database, version() AS version")
        return row or {}

    def close(self) -> None:
        with self._mutex:
            idle, self._idle = self._idle, []
        for wire in idle:
            self._close(wire)


def _error_message(raw: bytes, status: int) -> str:
    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return f"database returned {status}: {raw[:200]!r}"
    message = payload.get("message") or payload.get("error") or f"http {status}"
    hint = payload.get("hint")
    return f"{message}{f' ({hint})' if hint else ''}"


def _error_code(raw: bytes) -> str | None:
    try:
        return json.loads(raw or b"{}").get("code")
    except json.JSONDecodeError:
        return None


# --- schema ------------------------------------------------------------------

# Everything this backend owns. Deliberately additive: `CREATE TABLE IF NOT EXISTS`
# means a fresh Neon project and a database that has been running since October end
# up in the same shape. The auth tables next door (`neon_auth.*`) belong to Neon and
# are only ever read, never created here.
SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id           TEXT PRIMARY KEY,
    auth_user_id TEXT UNIQUE NOT NULL,
    email        TEXT NOT NULL,
    name         TEXT,
    created_at   TEXT NOT NULL,
    seeded_at    TEXT
);

CREATE TABLE IF NOT EXISTS wallets (
    user_id     TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    balance_ngn BIGINT NOT NULL,
    spent_ngn   BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS receipts (
    id             TEXT NOT NULL,
    user_id        TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    request_id     TEXT NOT NULL,
    bill_id        TEXT NOT NULL,
    bill_label     TEXT NOT NULL,
    meter          TEXT,
    amount_ngn     BIGINT NOT NULL,
    units          DOUBLE PRECISION,
    token          TEXT,
    tx_hash        TEXT,
    status         TEXT NOT NULL,
    entry_type     TEXT,
    source         TEXT,
    vendor         TEXT,
    vendor_code    TEXT,
    vendor_message TEXT,
    created_at     TEXT NOT NULL,
    seq            BIGSERIAL,
    -- The id is unique *per account*, not globally: every account is seeded from
    -- the same artboard history, so two accounts both own `rcpt_0001`.
    PRIMARY KEY (user_id, id),
    UNIQUE (user_id, request_id)
);

CREATE INDEX IF NOT EXISTS receipts_created ON receipts (user_id, created_at DESC, seq DESC);
CREATE INDEX IF NOT EXISTS receipts_pending ON receipts (user_id, bill_id, amount_ngn, status);

CREATE TABLE IF NOT EXISTS channel_identities (
    channel         TEXT NOT NULL,
    channel_user_id TEXT NOT NULL,
    user_id         TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    display_name    TEXT,
    linked_at       TEXT NOT NULL,
    last_seen_at    TEXT,
    PRIMARY KEY (channel, channel_user_id)
);

CREATE TABLE IF NOT EXISTS link_codes (
    code_hash  TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at    TEXT
);

CREATE TABLE IF NOT EXISTS link_attempts (
    channel         TEXT NOT NULL,
    channel_user_id TEXT NOT NULL,
    attempts        INTEGER NOT NULL,
    window_start    TEXT NOT NULL,
    PRIMARY KEY (channel, channel_user_id)
);

CREATE TABLE IF NOT EXISTS processed_messages (
    channel      TEXT NOT NULL,
    message_id   TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    PRIMARY KEY (channel, message_id)
);
"""


def ensure_schema(db: Database) -> None:
    """Create the tables. One statement per `CREATE`, since multi-statement is out.

    A database bootstrapped before 2026-10-26 has `receipts` keyed on `id` alone,
    which cannot hold two accounts' seeded histories. That table is replaced rather
    than migrated: it only ever held demo rows, and the next sign-in re-seeds.
    """
    exists = db.one(
        "SELECT 1 AS found FROM information_schema.tables"
        " WHERE table_schema = 'public' AND table_name = 'receipts'"
    )
    if exists is not None:
        legacy_key = db.one(
            "SELECT 1 AS legacy FROM pg_constraint"
            " WHERE conname = 'receipts_pkey' AND conrelid = 'public.receipts'::regclass"
            "   AND pg_get_constraintdef(oid) NOT LIKE '%user_id%'"
        )
        if legacy_key is not None:
            db.query("DROP TABLE IF EXISTS receipts")
    for statement in _statements(SCHEMA):
        db.query(statement)


def _statements(script: str) -> Iterable[str]:
    """Split the schema on semicolons that are not inside a quoted string.

    The script above has no functions or dollar-quoting, so this stays honest: it
    exists because the HTTP endpoint refuses to run more than one command at a time.
    """
    buffer: list[str] = []
    quote: str | None = None
    for char in script:
        if quote:
            buffer.append(char)
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            buffer.append(char)
            continue
        if char == ";":
            statement = "".join(buffer).strip()
            if statement:
                yield statement
            buffer = []
            continue
        buffer.append(char)
    tail = "".join(buffer).strip()
    if tail:
        yield tail


_open: Database | None = None
_open_lock = threading.Lock()


def open_database(*, required: bool = True) -> Database | None:
    """The process-wide database, opened once.

    Returns None when `DATABASE_URL` is unset and `required` is False, which is how
    the pure-unit tests (agent, policy, catalogue) keep running without a network.
    Anything that stores data asks for `required=True` and gets a clear error rather
    than a silent fallback to a file that no longer exists.
    """
    global _open
    with _open_lock:
        if _open is not None:
            return _open
        target = target_from_env()
        if target is None:
            if required:
                raise DatabaseError(
                    "DATABASE_URL is not set — copy apps/backend/.env.example to .env"
                )
            return None
        database = Database(target)
        ensure_schema(database)
        _open = database
        return database
