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

    def test_a_possessive_passes_through_untouched(self):
        self.assertEqual(wake_attempt("stark's meter"), "stark's meter")

    def test_nothing_else_is_rewritten(self):
        # The tail rule only ever removes the noun the name was said with.
        for said in ("stark please top up 5000", "stark what's my airtime",
                     "hey stark pay dstv tomorrow"):
            with self.subTest(said=said):
                self.assertEqual(wake_attempt(said), said)


class MisheardWakeWord(unittest.TestCase):
    def test_reported_mishearings_are_treated_as_addressed(self):
        for heard in ("start", "stop", "stock", "starn", "star", "stark",
                      "starp", "staark", "start what's my light bill",
                      "stock what's my light bill",
                      # 2026-10-25: the /k/ written every way a recogniser can.
                      "starquad", "starck", "starc", "starq", "starkk",
                      "starrk", "staaaark"):
            with self.subTest(heard=heard):
                self.assertIsNotNone(wake_attempt(heard), heard)

    def test_starquad_is_dropped_like_any_other_mishearing(self):
        # Reported 2026-10-25 from "hello stark what is left on my meter", heard
        # as one eight-letter token — four edits away, so the distance rule
        # alone stayed silent on a clip that was plainly addressed.
        self.assertEqual(wake_attempt("hello starquad what is left on my meter"),
                         "Stark, what is left on my meter")

    def test_a_split_mishearing_is_swallowed_whole(self):
        # "star quad" is one word the recogniser split; both halves are the
        # address, so neither may leak into the question.
        self.assertEqual(wake_attempt("star quad what's left"),
                         "Stark, what's left")
        self.assertEqual(wake_attempt("hey star quad how much is left"),
                         "Stark, how much is left")

    def test_every_way_a_recogniser_splits_the_name(self):
        """Two and three tokens, either half missing letters."""
        for said, wanted in (("star k how much is left", "Stark, how much is left"),
                             ("sta rk what is left", "Stark, what is left"),
                             ("st ar k what is left", "Stark, what is left"),
                             ("sto p", "Stark"),
                             ("hey star k what's my light bill",
                              "Stark, what's my light bill")):
            with self.subTest(said=said):
                self.assertEqual(wake_attempt(said), wanted)

    def test_a_hyphen_is_still_one_word(self):
        self.assertEqual(wake_attempt("star-k what is left"), "Stark, what is left")

    def test_the_noun_it_was_said_with_is_part_of_the_address(self):
        # "stark ai what is left" used to pass through whole, so the agent was
        # asked "ai what is left".
        self.assertEqual(wake_attempt("stark ai what is left"), "stark what is left")
        self.assertEqual(wake_attempt("hey stark ai, what's left"),
                         "hey stark what's left")
        self.assertEqual(wake_attempt("stark bot pay my dstv"), "stark pay my dstv")
        self.assertEqual(wake_attempt("star quad ai what is left"),
                         "Stark, what is left")

    def test_the_name_written_out_as_a_syllable(self):
        for heard in ("starky top up", "starkers how much", "starkey what's left",
                      "starkie how much is left"):
            with self.subTest(heard=heard):
                self.assertIsNotNone(wake_attempt(heard))

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
                     "is the stock still up",
                     # Near the new tolerance, and still not an address: "I" +
                     # "start" would join to something two edits from "stark".
                     "I start the car", "starboard is broken",
                     "starbucks is open", "quick question", "I'm stuck at work"):
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
