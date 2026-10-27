"""Short chat memory: the thing that makes a bare "500" mean something.

Hermetic — a clock is injected, so the TTL is tested without sleeping.
"""

from __future__ import annotations

import unittest

from app.modules.agent.memory import Threads


def _clock(start: float = 1_000.0):
    """A clock the test moves by hand, so ten minutes costs nothing."""
    now = [start]

    def read() -> float:
        return now[0]

    read.advance = lambda seconds: now.__setitem__(0, now[0] + seconds)
    return read


class Remembering(unittest.TestCase):
    def test_an_exchange_comes_back_in_order(self):
        threads = Threads()
        threads.remember("tg:1", "how much for airtime", "How much would you like?")
        self.assertEqual(threads.history("tg:1"), [
            {"role": "user", "content": "how much for airtime"},
            {"role": "assistant", "content": "How much would you like?"},
        ])

    def test_two_exchanges_stay_in_order(self):
        threads = Threads()
        threads.remember("tg:1", "top up my airtime", "How much?")
        threads.remember("tg:1", "500", "Paid ₦500 for airtime.")
        self.assertEqual([m["content"] for m in threads.history("tg:1")],
                         ["top up my airtime", "How much?", "500",
                          "Paid ₦500 for airtime."])

    def test_nothing_is_stored_without_both_halves(self):
        threads = Threads()
        threads.remember("tg:1", "", "How much?")
        threads.remember("tg:1", "500", None)
        threads.remember("tg:1", "500", "")
        self.assertEqual(threads.history("tg:1"), [])

    def test_no_thread_is_no_memory(self):
        threads = Threads()
        threads.remember(None, "500", "How much?")
        self.assertEqual(threads.history(None), [])
        self.assertEqual(threads.history(""), [])

    def test_history_is_a_copy(self):
        threads = Threads()
        threads.remember("tg:1", "500", "How much?")
        threads.history("tg:1").clear()
        self.assertEqual(len(threads.history("tg:1")), 2)


class Bounds(unittest.TestCase):
    def test_old_exchanges_fall_out(self):
        threads = Threads(max_turns=2)
        for n in range(4):
            threads.remember("tg:1", f"question {n}", f"answer {n}")
        said = [m["content"] for m in threads.history("tg:1")]
        self.assertEqual(said, ["question 2", "answer 2", "question 3", "answer 3"])

    def test_a_silent_ten_minutes_ends_the_conversation(self):
        clock = _clock()
        threads = Threads(ttl_seconds=600, clock=clock)
        threads.remember("tg:1", "top up my airtime", "How much?")
        clock.advance(599)
        self.assertEqual(len(threads.history("tg:1")), 2)
        clock.advance(2)
        self.assertEqual(threads.history("tg:1"), [])

    def test_a_live_chat_is_kept_alive_by_talking(self):
        clock = _clock()
        threads = Threads(ttl_seconds=600, clock=clock)
        threads.remember("tg:1", "top up my airtime", "How much?")
        clock.advance(500)
        threads.remember("tg:1", "500", "Paid ₦500 for airtime.")
        clock.advance(500)
        self.assertEqual(len(threads.history("tg:1")), 4)

    def test_a_chat_can_be_forgotten(self):
        threads = Threads()
        threads.remember("tg:1", "500", "How much?")
        threads.forget("tg:1")
        self.assertEqual(threads.history("tg:1"), [])

    def test_chats_do_not_see_each_other(self):
        threads = Threads()
        threads.remember("tg:1", "top up my airtime", "How much?")
        self.assertEqual(threads.history("tg:2"), [])

    def test_the_least_recently_used_chat_is_evicted(self):
        threads = Threads(max_threads=2)
        threads.remember("tg:1", "one", "one")
        threads.remember("tg:2", "two", "two")
        threads.history("tg:1")                      # tg:1 is now the newest
        threads.remember("tg:3", "three", "three")   # over the cap: tg:2 goes
        self.assertEqual(len(threads.history("tg:1")), 2)
        self.assertEqual(len(threads.history("tg:3")), 2)
        self.assertEqual(threads.history("tg:2"), [])


if __name__ == "__main__":
    unittest.main()
