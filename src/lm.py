"""Corpus loading, n-gram language model, Markov chain, word associations."""
from __future__ import annotations

import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from phonetics import tokenize

BOS, EOS = "<s>", "</s>"

STOPWORDS = set("""a an the and or but nor so yet for of to in on at by with from into upon over under
about as is are was were be been being am do does did doth dost hath hast have has had will would shall
should can could may might must i me my mine we us our ours you your yours thy thee thou thine ye he him
his she her hers it its they them their theirs this that these those who whom whose which what when where
how why not no if then than there here all any each some such too very just o oh yes
""".split())


# ------------------------------------------------------------------ corpus
@dataclass
class Poem:
    category: str
    stanzas: List[List[str]]              # raw text lines, grouped by stanza
    title: str = ""
    author: str = ""
    theme: Optional[str] = None
    meta: dict = field(default_factory=dict)
    source_idx: int = -1                  # index of source poem (reference units)

    @property
    def lines(self) -> List[str]:
        return [l for s in self.stanzas for l in s]

    @property
    def token_lines(self) -> List[List[str]]:
        return [t for t in (tokenize(l) for l in self.lines) if t]

    def text(self) -> str:
        return "\n\n".join("\n".join(s) for s in self.stanzas)


class Corpus:
    """The inspiring set. Blank lines in the JSON mark stanza breaks."""

    def __init__(self, path: str):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        self.comment = d.get("_comment", "")
        self.categories: Dict[str, str] = d["categories"]
        self.poems: List[Poem] = []
        for i, p in enumerate(d["poems"]):
            stanzas, cur = [], []
            for l in p["lines"]:
                if l.strip():
                    cur.append(l.strip())
                elif cur:
                    stanzas.append(cur)
                    cur = []
            if cur:
                stanzas.append(cur)
            self.poems.append(Poem(p["category"], stanzas, p["title"], p["author"], source_idx=i,
                                   meta={"excerpt": p.get("excerpt", False)}))
        self.vocab = {w for p in self.poems for tl in p.token_lines for w in tl}

    def of_category(self, cat: str) -> List[Poem]:
        return [p for p in self.poems if p.category == cat]

    def reference_units(self, cat: str) -> List[Poem]:
        """Real poems cut to the unit the generator produces: quatrain -> each
        4-line stanza, sonnet -> whole poem, free verse -> whole poem."""
        units = []
        for p in self.of_category(cat):
            if cat == "quatrain":
                for s in p.stanzas:
                    if len(s) == 4:
                        units.append(Poem(cat, [s], p.title, p.author, source_idx=p.source_idx))
            else:
                units.append(Poem(cat, p.stanzas, p.title, p.author, source_idx=p.source_idx))
        return units

    def line_ngram_sets(self, max_n: int = 6) -> Dict[int, set]:
        sets = {n: set() for n in range(2, max_n + 1)}
        for p in self.poems:
            for tl in p.token_lines:
                for n in sets:
                    for i in range(len(tl) - n + 1):
                        sets[n].add(tuple(tl[i:i + n]))
        return sets

    def line_set(self) -> set:
        return {tuple(tl) for p in self.poems for tl in p.token_lines}


# ------------------------------------------------------ n-gram LM (scoring)
class NgramLM:
    """Interpolated unigram/bigram model used to measure *typicality*."""

    def __init__(self, vocab_size: int, lambdas=(0.55, 0.40, 0.05)):
        self.V = vocab_size + 2
        self.l2, self.l1, self.l0 = lambdas
        self.uni: Counter = Counter()
        self.bi: Dict[str, Counter] = defaultdict(Counter)
        self.ctx: Counter = Counter()
        self.total = 0

    def fit(self, token_lines: List[List[str]]) -> "NgramLM":
        for tl in token_lines:
            seq = [BOS] + tl + [EOS]
            for a, b in zip(seq, seq[1:]):
                self.uni[b] += 1
                self.bi[a][b] += 1
                self.ctx[a] += 1
                self.total += 1
        return self

    def prob(self, prev: str, w: str) -> float:
        pu = (self.uni[w] + 0.1) / (self.total + 0.1 * self.V)
        if self.ctx[prev] == 0:
            return (self.l1 + self.l2) * pu + self.l0 / self.V
        pb = self.bi[prev][w] / self.ctx[prev]
        return self.l2 * pb + self.l1 * pu + self.l0 / self.V

    def mean_logprob(self, token_lines: List[List[str]]) -> float:
        tot, n = 0.0, 0
        for tl in token_lines:
            seq = [BOS] + tl + [EOS]
            for a, b in zip(seq, seq[1:]):
                tot += math.log(self.prob(a, b))
                n += 1
        return tot / n if n else float("-inf")


# ----------------------------------------------------- Markov chain (generator)
class MarkovModel:
    """Order-2 word chain (with order-1 mixing) over poem lines.

    Trained in BOTH directions: the forward chain is used for free verse,
    the backward chain lets us start a line from its rhyme word and walk
    towards the beginning, which is how rhyme is enforced by construction.

    Every poem in the corpus contributes, but poems of the target category
    count `cat_weight` times more, so a small category borrows vocabulary
    and transitions from the others without losing its own voice.
    """

    def __init__(self, corpus: Corpus, category: str, cat_weight: float = 4.0,
                 order2_weight: float = 0.6):
        self.lam = order2_weight
        self.f2: Dict[tuple, Counter] = defaultdict(Counter)
        self.f1: Dict[str, Counter] = defaultdict(Counter)
        self.b2: Dict[tuple, Counter] = defaultdict(Counter)
        self.b1: Dict[str, Counter] = defaultdict(Counter)
        self.word_count: Counter = Counter()
        for p in corpus.poems:
            w = cat_weight if p.category == category else 1.0
            for tl in p.token_lines:
                self._add(self.f2, self.f1, [BOS, BOS] + tl + [EOS], w)
                self._add(self.b2, self.b1, [EOS, EOS] + tl[::-1] + [BOS], w)
                for t in tl:
                    self.word_count[t] += w
        self.starts = self.f2[(BOS, BOS)]
        self.ends = self.b2[(EOS, EOS)]
        self.total_starts = sum(self.starts.values())

    @staticmethod
    def _add(t2, t1, seq, w):
        for i in range(2, len(seq)):
            t2[(seq[i - 2], seq[i - 1])][seq[i]] += w
            t1[seq[i - 1]][seq[i]] += w

    def start_p(self, w: str) -> float:
        return self.starts.get(w, 0.0) / self.total_starts

    def has_predecessor(self, w: str) -> bool:
        return any(k != BOS for k in self.b1.get(w, ()))

    def sample(self, direction: str, ctx: Tuple[str, str], rng: random.Random,
               weight_fn: Optional[Callable[[str], float]] = None) -> Optional[str]:
        """Sample the next token. `weight_fn(x)` returns a multiplier (0 = forbidden)."""
        t2, t1 = (self.f2, self.f1) if direction == "f" else (self.b2, self.b1)
        c2, c1 = t2.get(ctx), t1.get(ctx[1])
        if not c1:
            return None
        s1 = sum(c1.values())
        s2 = sum(c2.values()) if c2 else 0.0
        cands: Dict[str, float] = {}
        for x, c in c1.items():
            cands[x] = (1 - self.lam) * c / s1 if s2 else c / s1
        if s2:
            for x, c in c2.items():
                cands[x] = cands.get(x, 0.0) + self.lam * c / s2
        if weight_fn:
            cands = {x: p * weight_fn(x) for x, p in cands.items()}
        items = [(x, p) for x, p in cands.items() if p > 0]
        if not items:
            return None
        return rng.choices([x for x, _ in items], weights=[p for _, p in items])[0]


# --------------------------------------------- word associations (coherence)
class Associations:
    """Positive PMI between content words that occur within +-`window` lines.

    This is the lightweight stand-in for word embeddings (the NLG slides'
    'meaning is use' idea): two words are related if they keep appearing in
    the same neighbourhood of a poem. Used for (a) steering a poem towards
    a theme and (b) measuring how well its lines hang together.
    """

    def __init__(self, corpus: Corpus, window: int = 2, min_pair: int = 2):
        self.count: Counter = Counter()
        self.pair: Dict[str, Counter] = defaultdict(Counter)
        self.N = 0
        for p in corpus.poems:
            lines = [{w for w in tl if w not in STOPWORDS and len(w) > 2} for tl in p.token_lines]
            for i, l in enumerate(lines):
                ctx = set()
                for j in range(max(0, i - window), min(len(lines), i + window + 1)):
                    ctx |= lines[j]
                self.N += 1
                for w in l:
                    self.count[w] += 1
                    for v in ctx:
                        if v != w:
                            self.pair[w][v] += 1
        self.min_pair = min_pair
        self._vec_cache: Dict[str, Dict[str, float]] = {}

    def ppmi(self, w: str, v: str) -> float:
        c = self.pair[w].get(v, 0)
        if c < self.min_pair:
            return 0.0
        return max(0.0, math.log(c * self.N / (self.count[w] * self.count[v])))

    def vector(self, w: str) -> Dict[str, float]:
        if w not in self._vec_cache:
            self._vec_cache[w] = {v: s for v in self.pair.get(w, {}) if (s := self.ppmi(w, v)) > 0}
        return self._vec_cache[w]

    def neighbours(self, theme: str, k: int = 40) -> Dict[str, float]:
        vec = self.vector(theme)
        return dict(sorted(vec.items(), key=lambda kv: -kv[1])[:k])

    def theme_boost(self, theme: str) -> Dict[str, float]:
        """Multiplier per word: the theme itself x8, its neighbours up to x7."""
        nb = self.neighbours(theme)
        if not nb:
            return {theme: 8.0}
        top = max(nb.values())
        boost = {w: 1.0 + 6.0 * s / top for w, s in nb.items()}
        boost[theme] = 8.0
        return boost

    def line_vector(self, tokens: List[str]) -> Dict[str, float]:
        out: Dict[str, float] = defaultdict(float)
        for t in tokens:
            if t in STOPWORDS:
                continue
            for v, s in self.vector(t).items():
                out[v] += s
        return out

    @staticmethod
    def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(s * b.get(k, 0.0) for k, s in a.items())
        na = math.sqrt(sum(s * s for s in a.values()))
        nb = math.sqrt(sum(s * s for s in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    def candidate_themes(self, min_count: int = 5) -> List[str]:
        return [w for w, c in self.count.items() if c >= min_count and len(self.vector(w)) >= 5]
