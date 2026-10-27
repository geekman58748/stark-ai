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
    wake_attempt("Hello Starquad is left?")      ->  "Stark, is left?"
    wake_attempt("what's the weather")           ->  None
"""

from __future__ import annotations

import re

WAKE = "stark"

# Two edits from "stark" already covers start, stock, starn, star, stack, stork.
# This holds the ones a distance rule cannot reach without also swallowing
# ordinary words: `stop` is three edits away but was genuinely heard in place of
# the wake word. Grow it only from transcripts somebody actually reported.
#
# 2026-10-25: "Starquad", from "hello stark what is left on my meter" — one
# eight-letter token for a five-letter name, four edits away, so the distance
# rule alone stayed silent on a clip that was plainly addressed.
#
# The rest are the name written out the way people and recognisers do when the
# /k/ becomes a syllable or a surname: Starky, Starkie, Starkey. They are all
# further than two edits once the /k/ is folded, and all plainly the address.
_ALIASES = frozenset({"stop", "starquad", "starky", "starkie", "starkee",
                      "starkey", "starkers"})

# The product name said with its noun attached — "stark ai", "stark bot". The
# noun is part of the address, not the first word of the question, so it is
# dropped with the wake word. Otherwise the agent is asked "ai what is left".
_TAILS = frozenset({"ai", "a.i.", "bot", "assistant", "agent", "app"})

# Words that may sit in front of the wake word without meaning anything — so the
# attempt is looked for in the first few tokens, not only the first: people say
# "hey start…", "um stark…", "so start what's my light bill".
_FILLERS = frozenset({"hey", "hi", "hello", "um", "uh", "er", "ah", "so",
                      "yeah", "yes", "ok", "okay", "please", "stark"})
_WINDOW = 3          # how far into the utterance to keep looking for the address
_MAX_JOIN = 3        # how many tokens a split name may be spread across

_WORD = re.compile(r"\bstark\b", re.IGNORECASE)
_EDGES = ".,!?;:\"'"

# The /k/ in "stark" gets spelled every way a recogniser can manage: starck,
# starc, starq, starquad. Folding those onto one letter keeps the rule at "two
# edits" instead of needing an alias per spelling.
_FOLDS = (("qu", "k"), ("ck", "k"), ("c", "k"), ("q", "k"))


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


def _normalise(word: str) -> str:
    """One spelling to compare against: fold the /k/, collapse stutters.

    "staaaark" and "starkk" are the same word said slowly and typed badly, and
    "starquad" is the same /k/ written out — after this they are all close to
    "stark" by the same two-edit rule.
    """
    folded = word
    for spelling, letter in _FOLDS:
        folded = folded.replace(spelling, letter)
    return re.sub(r"(.)\1+", r"\1", folded)


def _is_wake_attempt(word: str) -> bool:
    if not word:
        return False
    if word in _ALIASES:
        return True
    folded = _normalise(word)
    if folded in _ALIASES:
        return True
    # Short words are how "so", "it", "on" become wake words; the wake word is
    # four letters, so anything shorter is not an attempt at it.
    return len(folded) >= 4 and _edits(folded, WAKE) <= 2


def _looks_like_head(word: str) -> bool:
    """Could this token be the first half of the name? "st…", not "i".

    Two letters is enough because the halves can be tiny — "st ar k" is a
    recogniser spelling the name out — and the join is only accepted when the
    whole thing lands on the wake word. What this guard really stops is an
    ordinary word welded to the next one: "I" + "start" would otherwise join
    to "istart", two edits from "stark".
    """
    folded = _normalise(word)
    return len(folded) >= 2 and WAKE.startswith(folded[:2])


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
        return _without_tail(said)

    words = said.split(" ")
    # Look for an attempt in the first few tokens, but only behind filler: the
    # utterance has to *open* with the address (possibly after "hey" or "um"),
    # not stumble into it — "I start the car" is not a wake word.
    for at in range(min(_WINDOW, len(words))):
        if any(words[p].lower().strip(_EDGES) not in _FILLERS
               for p in range(at)):
            break
        first = words[at].lower().strip(_EDGES)
        if first in _FILLERS:
            continue
        # One word split by the recogniser: "star quad", "star k", "st ar k",
        # "sto p". Try the joins before the single token, longest first, so the
        # leftover half is part of the address rather than the first word of the
        # question — "star quad what's left" must not become "Stark, quad
        # what's left".
        if _looks_like_head(first):
            for take in range(_MAX_JOIN, 1, -1):
                if at + take > len(words):
                    continue
                joined = first + "".join(
                    w.lower().strip(_EDGES) for w in words[at + 1:at + take])
                if _is_wake_attempt(joined):
                    return _addressed(words[at + take:])
        if _is_wake_attempt(first):
            return _addressed(words[at + 1:])
    return None


def _addressed(rest: list[str]) -> str:
    """The utterance with filler and the misheard token replaced by the address."""
    said = " ".join(_without_tail_words(rest))
    return f"{WAKE.capitalize()}, {said}" if said else WAKE.capitalize()


def _without_tail_words(words: list[str]) -> list[str]:
    """Drop a noun the name was said with — "ai", "bot" — from the front."""
    if words and words[0].lower().strip(_EDGES) in _TAILS:
        return words[1:]
    return words


def _without_tail(said: str) -> str:
    """The same, on the pass-through path, without touching anything else."""
    found = _WORD.search(said)
    head, rest = said[:found.end()], said[found.end():]
    after = rest.lstrip(" ,.!?")
    if after:
        word, _, tail = after.partition(" ")
        if word.lower().strip(_EDGES) in _TAILS:
            rest = f" {tail}" if tail else ""
    return (head + rest).strip()
