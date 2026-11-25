from __future__ import annotations

import math
import random
from collections import Counter
from itertools import combinations
from typing import List, Tuple

from lm import STOPWORDS
from metrics import DANGLING
from phonetics import tokenize

DET = {"the", "a", "an", "my", "thy", "your", "our", "this", "that", "his", "her", "their", "its", "no"}
PREP = {"in", "on", "at", "of", "to", "with", "from", "into", "upon", "over", "for", "by"}
SMALL = {"a", "an", "the", "of", "in", "on", "at", "to", "and", "or", "for", "with", "from", "by",
         "into", "upon", "over"}
LEN_FIT = {1: 0.6, 2: 1.0, 3: 1.0, 4: 0.8}


class Titler:
    def __init__(self, corpus, evaluator):
        self.ev = evaluator
        self.real = {tuple(tokenize(p.title)) for p in corpus.poems}
        count: Counter = Counter()
        after_det: Counter = Counter()
        before_content: Counter = Counter()       
        doc_freq: Counter = Counter()
        for p in corpus.poems:
            doc_freq.update({w for tl in p.token_lines for w in tl})
            for tl in p.token_lines:
                for i, w in enumerate(tl):
                    count[w] += 1
                    if i and tl[i - 1] in DET:
                        after_det[w] += 1
                    if i + 1 < len(tl) and tl[i + 1] not in STOPWORDS:
                        before_content[w] += 1
        self.noun_like = {w for w, c in count.items()
                          if after_det[w] >= 1 and after_det[w] / c >= 0.25
                          and before_content[w] / c <= 0.6
                          and w not in STOPWORDS and len(w) > 2}
        n = len(corpus.poems)
        self.distinct = {w: math.log((n + 1) / (d + 1)) / math.log(n + 1) for w, d in doc_freq.items()}

    # ------------------------------------------------------------- candidates
    def _ok(self, span: Tuple[str, ...]) -> bool:
        last = span[-1]
        if last in STOPWORDS or last in DANGLING or len(last) < 3:
            return False
        if len(set(span)) < len(span):
            return False
        if len(span) == 1 and last not in self.noun_like:
            return False
        first = span[0]
        if first == "of":
            return False                               
        if first in STOPWORDS:
            if first in DET:
                if len(span) < 2:
                    return False
            elif first in PREP:
                if len(span) < 3 or span[1] not in DET:
                    return False
            else:
                return False                     
        for a, b in zip(span, span[1:]):
            if a in STOPWORDS and b in STOPWORDS and not (a in PREP and b in DET):
                return False
        return True

    def _candidates(self, poem, salience):
        cands = set()
        for tl in poem.token_lines:
            for n in range(1, 5):
                for i in range(len(tl) - n + 1):
                    span = tuple(tl[i:i + n])
                    if self._ok(span):
                        cands.add(span)
        nouns = [w for w in sorted(salience, key=lambda w: -salience[w]) if w in self.noun_like][:3]
        for w in nouns:
            cands.add((w,))
            cands.add(("the", w))
        for a, b in combinations(nouns, 2):
            cands.add((a, "and", b))
        return {c for c in cands if c not in self.real}

    def _score(self, span, salience) -> float:
        content = [w for w in span if w not in STOPWORDS]
        sal = sum(salience.get(w, 0.0) for w in content) / len(content) if content else 0.0
        syn = self.ev.syntax_score([list(span)])
        noun = 1.0 if span[-1] in self.noun_like else 0.0
        dist = sum(self.distinct.get(w, 1.0) for w in content) / len(content) if content else 0.0
        return 0.25 * sal + 0.25 * syn + 0.20 * noun + 0.10 * LEN_FIT[len(span)] + 0.20 * dist

    # ------------------------------------------------------------------ title
    @staticmethod
    def _format(span) -> str:
        out = []
        for i, w in enumerate(span):
            if w == "i" or w.startswith("i'"):
                w = "I" + w[1:]
            elif w == "o":
                w = "O"
            elif i in (0, len(span) - 1) or w not in SMALL:
                w = w[0].upper() + w[1:]
            out.append(w)
        return " ".join(out)

    def title(self, poem, plan, avoid=()) -> str:
        """`avoid`: titles already used in this run (case-insensitive); never repeated."""
        plan_words = set(plan.theme) | set(plan.counter)
        counts = Counter(w for tl in poem.token_lines for w in tl if w not in STOPWORDS)
        salience = {w: 0.5 * min(1.0, c / 2) + (0.5 if w in plan_words else 0.0) for w, c in counts.items()}
        taken = {t.lower() for t in avoid}
        cands = {c for c in self._candidates(poem, salience) if self._format(c).lower() not in taken}
        if not cands:
            return plan.theme[0].capitalize()
        ranked = sorted(cands, key=lambda c: (-self._score(c, salience), c))[:3]
        rng = random.Random(" ".join(poem.lines))      
        return self._format(rng.choices(ranked, weights=[3, 2, 1][:len(ranked)])[0])
