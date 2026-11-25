"""Phonetic helpers: tokenisation, syllables, stress, rhyme, meter.

Everything here is built on the CMU Pronouncing Dictionary (via the
`pronouncing` package). Words missing from the dictionary fall back to a
vowel-group syllable heuristic and are never used as rhyme words.
"""
from __future__ import annotations

import functools
import re
from typing import List, Optional

import pronouncing

WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)*")


# Small function words are normally unstressed in speech. In meter_fit they may sit on a
# strong beat, but it costs half a point (poets do this, but rarely a whole line of it).
WEAK_WORDS = set("""the a an and or but nor so of to in on at by with from for as if than
is are was were be am my thy his her its our your their i me we you he she it they that this
""".split())


def tokenize(line: str) -> List[str]:
    """Lower-case word tokens. '&' and punctuation are dropped."""
    return WORD_RE.findall(line.lower().replace("’", "'"))


@functools.lru_cache(maxsize=None)
def phones(word: str) -> Optional[str]:
    """First CMU pronunciation of `word`, or None if unknown."""
    cands = pronouncing.phones_for_word(word)
    if not cands and word.endswith("'s"):
        cands = pronouncing.phones_for_word(word[:-2])
    return cands[0] if cands else None


def in_dictionary(word: str) -> bool:
    return phones(word) is not None


def _heuristic_syllables(word: str) -> int:
    groups = re.findall(r"[aeiouy]+", word)
    n = len(groups)
    if word.endswith("e") and n > 1 and not word.endswith(("le", "ee")):
        n -= 1
    return max(1, n)


@functools.lru_cache(maxsize=None)
def syllables(word: str) -> int:
    p = phones(word)
    if p is None:
        return _heuristic_syllables(word)
    return max(1, pronouncing.syllable_count(p))


@functools.lru_cache(maxsize=None)
def stress(word: str) -> str:
    """Stress string: '1' stressed, '0' unstressed, 'x' flexible, 'w' weak function word.

    Content monosyllables and secondary stress stay flexible. Monosyllabic function
    words are 'w': fine on a weak beat, mildly penalised on a strong one.
    Unknown words are flexible throughout.
    """
    p = phones(word)
    if p is None:
        return "x" * syllables(word)
    raw = pronouncing.stresses(p)
    if len(raw) <= 1:
        return "w" if word in WEAK_WORDS else "x" * max(1, len(raw))
    return "".join("1" if c == "1" else ("0" if c == "0" else "x") for c in raw)


def line_syllables(tokens: List[str]) -> int:
    return sum(syllables(t) for t in tokens)


def line_stress(tokens: List[str]) -> str:
    return "".join(stress(t) for t in tokens)


# ---------------------------------------------------------------- rhyme
@functools.lru_cache(maxsize=None)
def rhyme_key(word: str) -> Optional[str]:
    p = phones(word)
    return pronouncing.rhyming_part(p) if p else None


def is_rhyme(a: str, b: str) -> bool:
    """True rhyme: same rhyming part, different word, and not a compound of
    the other (light/delight is an 'identical rhyme' and is rejected)."""
    if a == b:
        return False
    ka, kb = rhyme_key(a), rhyme_key(b)
    if ka is None or kb is None or ka != kb:
        return False
    if a.endswith(b) or b.endswith(a):
        return False
    return True


# ---------------------------------------------------------------- meter
def meter_template(n: int, kind: str) -> str:
    """'iambic' -> 0101..., 'trochaic' -> 1010..., truncated to n syllables."""
    base = "01" if kind == "iambic" else "10"
    return (base * (n // 2 + 1))[:n]


def meter_fit(tokens: List[str], template: str) -> float:
    """1.0 = the line's lexical stress matches the template everywhere
    (flexible syllables always match); extra/missing syllables count as
    mismatches."""
    s = line_stress(tokens)
    n = max(len(s), len(template))
    if n == 0:
        return 0.0
    bad = float(abs(len(s) - len(template)))
    for a, b in zip(s, template):
        if (a == "1" and b == "0") or (a == "0" and b == "1"):
            bad += 1.0
        elif a == "w" and b == "1":
            bad += 0.5
    return max(0.0, 1.0 - bad / n)
