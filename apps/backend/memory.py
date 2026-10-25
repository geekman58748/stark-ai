"""The last few turns of one chat, so a reply can read its own last sentence.

Every turn used to be answered cold: `Agent.respond` was handed one string and
nothing else, so a message that carried only half an answer had no anchor for the
other half. Measured 2026-10-25 on Telegram, in one conversation:

    "top up my number with airtime"  -> "How much would you like to use?"
    "500"                            -> "Which bill would you like to pay 500 for?"
    "airtime"                        -> "How much would you like to pay?"
    "500"                            -> "Which bill would you like to pay 500 for?"

It was not looping out of stubbornness — each reply had forgotten the half the
previous one supplied. Replayed cold against the same model, that bare "500" paid
the *electricity* bill instead, because with no antecedent the number attached
itself to whichever bill was nearest.

This is not a transcript and not a log. `turnlog` is the record of what happened;
this is only what the model needs in front of it to make sense of the next line.
Two rules keep it from becoming a stale pile:

  * **Bounded** — the last `max_turns` exchanges per chat, nothing older.
  * **Stale is gone** — a thread untouched for `ttl_seconds` is dropped, so a
    "500" tomorrow morning does not settle a question asked last night.

In memory, per process: a restart forgets the conversation, which is the right
amount of durable for a demo and the wrong amount for a product. Nothing secret
goes in — the same words already went to the model.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict

MAX_TURNS = 6          # exchanges kept per chat: enough for "and how much?"
TTL_SECONDS = 600      # ten minutes of silence ends the conversation
MAX_THREADS = 256      # chats tracked at once, so an open door cannot grow forever


class Threads:
    """A fixed-size, time-limited map of chat → recent messages."""

    def __init__(self, max_turns: int = MAX_TURNS, ttl_seconds: float = TTL_SECONDS,
                 max_threads: int = MAX_THREADS,
                 clock=time.monotonic) -> None:
        self.max_turns = max(1, int(max_turns))
        self.ttl_seconds = float(ttl_seconds)
        self.max_threads = max(1, int(max_threads))
        self._clock = clock
        self._lock = threading.Lock()
        # Ordered so the least recently used chat is the one evicted; the
        # request handler is threaded, so this is shared state.
        self._chats: OrderedDict[str, tuple[float, list[dict]]] = OrderedDict()

    def history(self, thread: str | None) -> list[dict]:
        """The messages to put in front of the new one — oldest first."""
        if not thread:
            return []
        with self._lock:
            held = self._chats.get(thread)
            if held is None:
                return []
            if self._expired(held[0]):
                self._chats.pop(thread, None)
                return []
            self._chats.move_to_end(thread)
            return [dict(message) for message in held[1]]

    def remember(self, thread: str | None, heard: str, said: str | None) -> None:
        """Keep one exchange. Nothing is stored without both halves."""
        if not thread or not heard or not said:
            return
        with self._lock:
            held = self._chats.get(thread)
            messages = [] if held is None or self._expired(held[0]) else held[1]
            messages = messages + [
                {"role": "user", "content": heard},
                {"role": "assistant", "content": said},
            ]
            # Two messages per exchange, oldest dropped first.
            messages = messages[-2 * self.max_turns:]
            self._chats[thread] = (self._clock(), messages)
            self._chats.move_to_end(thread)
            while len(self._chats) > self.max_threads:
                self._chats.popitem(last=False)

    def forget(self, thread: str | None) -> None:
        """Drop a chat's history — `/unlink`, or a test cleaning up."""
        if not thread:
            return
        with self._lock:
            self._chats.pop(thread, None)

    def _expired(self, touched: float) -> bool:
        return (self._clock() - touched) > self.ttl_seconds
