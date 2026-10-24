"""Wake words: one rule, one implementation.

`/v1/voice` and the Telegram voice path both ask the same question — *was this
utterance aimed at Stark?* The rule used to be `"stark" in transcript.lower()`,
which is right about people and wrong about recognizers: a browser returned
`start`, `stock`, `starn` and `stop` for a spoken "stark" (reported 2026-10-24
on `en-NG`), so somebody who *did* say the wake word was told they hadn't.

So the gate now tolerates the mishearing the way texting tolerates a typo. A
transcript that begins with a plausible attempt at the wake word is rewritten as
an addressed one — the misheard token is dropped, `Stark,` goes on the front —
and the agent, which only ever reads the words *after* the wake, cannot tell the
difference. Anything that does not look like an attempt stays ignored, because a
wake gate that fires on every sentence is not a gate.

    wake_attempt("start what's my light bill")  ->  "Stark, what's my light bill"
    wake_attempt("hey starn")                   ->  "Stark"
    wake_attempt("what's the weather")           ->  None
"""

from __future__ import annotations

import re

WAKE = "stark"

# Two edits from "stark" already covers start, stock, starn, star, stack, stork.
# This holds the ones a distance rule cannot reach without also swallowing
# ordinary words: `stop` is three edits away but was genuinely heard in place of
# the wake word. Grow it only from transcripts somebody actually reported.
_ALIASES = frozenset({"stop"})

# Words that may sit in front of the wake word without meaning anything — so the
# attempt is looked for in the first few tokens, not only the first: people say
# "hey start…", "um stark…", "so start what's my light bill".
_FILLERS = frozenset({"hey", "hi", "hello", "um", "uh", "er", "ah", "so",
                      "yeah", "yes", "ok", "okay", "please", "stark"})
_WINDOW = 3          # how far into the utterance to keep looking for the address

_WORD = re.compile(r"\bstark\b", re.IGNORECASE)
_LEADING = ".,!?"


def _edits(a: str, b: str, limit: int = 2) -> int:
    """Levenshtein distance, cheaply abandoned once it cannot get under `limit`."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (ca != cb)))
        if min(current) > limit:
            return limit + 1
        previous = current
    return previous[-1]


def _is_wake_attempt(word: str) -> bool:
    if word in _ALIASES:
        return True
    # Short words are how "so", "it", "on" become wake words; the wake word is
    # four letters, so anything shorter is not an attempt at it.
    return len(word) >= 4 and _edits(word, WAKE) <= 2


def wake_attempt(text: str | None) -> str | None:
    """The transcript to hand the agent, or `None` when nobody was addressed.

    Keeps the wording exactly as heard — only the misheard wake token is
    removed and the address put back — so the model still sees the user's own
    phrasing, typos and jargon included.
    """
    said = " ".join((text or "").split())
    if not said:
        return None
    if _WORD.search(said):                      # said it properly, anywhere
        return said

    words = said.split(" ")
    # Look for an attempt in the first few tokens, but only behind filler: the
    # utterance has to *open* with the address (possibly after "hey" or "um"),
    # not stumble into it — "I start the car" is not a wake word.
    for at in range(min(_WINDOW, len(words))):
        if any(words[p].lower().strip(_LEADING) not in _FILLERS
               for p in range(at)):
            break
        first = words[at].lower().strip(_LEADING)
        if first not in _FILLERS and _is_wake_attempt(first):
            rest = words[at + 1:]       # drop filler and the misheard word
            return f"{WAKE.capitalize()}, {' '.join(rest)}" if rest else WAKE.capitalize()
    return None
