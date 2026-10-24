"""The wake gate's typo tolerance, pinned to the mishearings actually reported.

Hermetic: this is a pure function, so no server, no model, no network.
"""

from __future__ import annotations

import unittest

from wake import wake_attempt


class SpokenProperly(unittest.TestCase):
    def test_said_wake_word_passes_through_untouched(self):
        for said in ("stark what's my light bill", "Stark, top up with 5000 naira",
                     "hey stark how much is left", "hello stark what's left"):
            with self.subTest(said=said):
                self.assertEqual(wake_attempt(said), said)

    def test_wake_word_in_the_middle_still_counts(self):
        self.assertEqual(wake_attempt("what is my stark light bill"),
                         "what is my stark light bill")


class MisheardWakeWord(unittest.TestCase):
    def test_reported_mishearings_are_treated_as_addressed(self):
        for heard in ("start", "stop", "stock", "starn", "star", "stark",
                      "starp", "staark", "start what's my light bill",
                      "stock what's my light bill"):
            with self.subTest(heard=heard):
                self.assertIsNotNone(wake_attempt(heard), heard)

    def test_the_misheard_token_is_dropped_and_the_address_restored(self):
        self.assertEqual(wake_attempt("start what's my light bill"),
                         "Stark, what's my light bill")
        self.assertEqual(wake_attempt("starn top up my airtime"),
                         "Stark, top up my airtime")

    def test_hey_plus_a_mishearing_is_dropped_together(self):
        self.assertEqual(wake_attempt("hey start what's my light bill"),
                         "Stark, what's my light bill")
        self.assertEqual(wake_attempt("hey stop"), "Stark")

    def test_wake_only_still_reaches_the_agent(self):
        self.assertEqual(wake_attempt("start"), "Stark")
        self.assertEqual(wake_attempt("starn!"), "Stark")

    def test_the_rest_of_the_utterance_keeps_its_own_typos(self):
        self.assertEqual(wake_attempt("start how much have I spent"),
                         "Stark, how much have I spent")

    def test_filler_words_in_front_do_not_hide_the_address(self):
        for said in ("um start what's my light bill",
                     "so start what's my light bill",
                     "hey starn top up my airtime",
                     "okay stop what's my light bill"):
            with self.subTest(said=said):
                self.assertEqual(wake_attempt(said),
                                 "Stark, " + said.split(" ", 1)[1].split(" ", 1)[1])


class NotAnAddress(unittest.TestCase):
    def test_ordinary_speech_is_still_ignored(self):
        for said in ("what's the weather", "top up my airtime with 1000 naira",
                     "the state of the grid", "starting the car",
                     "stopping at the shop", "I start the car",
                     "is the stock still up"):
            with self.subTest(said=said):
                self.assertIsNone(wake_attempt(said), said)

    def test_too_short_a_word_is_not_an_attempt(self):
        for said in ("so", "it", "on", "st"):
            with self.subTest(said=said):
                self.assertIsNone(wake_attempt(said), said)

    def test_empty_and_none_are_nothing(self):
        self.assertIsNone(wake_attempt(""))
        self.assertIsNone(wake_attempt(None))
        self.assertIsNone(wake_attempt("   ,,,  "))


if __name__ == "__main__":
    unittest.main()
