"""Poem generator: Markov chains + rhyme/meter constraints + a Plan + generate-and-rank.

How a poem is built
  1. A Plan: premise, imagery, length; each stanza gets a role.
  2. Each role boosts different words, so the poem develops instead of repeating one theme.
  3. Rhyme: all end words are picked first (one rhyme family per rhyme letter).
  4. Lines are built IN READING ORDER, each backwards from its end word with the reverse
     Markov chain, so rhyme and syllable count hold by construction.
  5. Each line is chosen from a pool of valid candidates by a local score that includes
     how well it connects to the PREVIOUS line.
  6. Several whole poems are generated and ranked with the evaluator.
Free verse has no rhyme or meter, so lines are sampled forwards.
"""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from lm import Associations, Corpus, MarkovModel, Poem, BOS, EOS, STOPWORDS
from metrics import Evaluator, SONNET_BREAKS, SONNET_SCHEME, clip
from phonetics import (in_dictionary, is_rhyme, meter_fit, meter_template, rhyme_key,
                       syllables, tokenize)
from planner import Plan, make_plan, outline, role_boost, stop_check

QUATRAIN_PATTERNS = [            # (syllables per line, meter kind, weight)
    ((8, 6, 8, 6), "iambic", 0.40),      # common / ballad metre (Dickinson, hymns)
    ((8, 8, 8, 8), "iambic", 0.30),      # iambic tetrameter
    ((7, 7, 7, 7), "trochaic", 0.30),    # catalectic trochaic (Blake, nursery rhymes)
]
MAX_WORDS = 13


@dataclass
class GenConfig:
    cat_weight: float = 4.0          # how much the target category outweighs the rest
    order2_weight: float = 0.6       # trigram vs bigram mixing (lower = more novel)
    line_pool: int = 24              # valid candidate lines to collect per slot
    poem_pool: int = 12              # whole poems generated before ranking
    group_retries: int = 25          # re-picks of the rhyme plan if a line fails to build
    max_copy_ngram: int = 5          # reject lines containing a copied n-gram this long


class PoemGenerator:
    def __init__(self, corpus: Corpus, category: str, config: Optional[GenConfig] = None,
                 seed: Optional[int] = None, evaluator: Optional[Evaluator] = None):
        assert category in corpus.categories, f"unknown category {category}"
        self.corpus, self.category = corpus, category
        self.cfg = config or GenConfig()
        self.rng = random.Random(seed)
        self.model = MarkovModel(corpus, category, self.cfg.cat_weight, self.cfg.order2_weight)
        self.assoc = evaluator.assoc if evaluator else Associations(corpus)
        self.evaluator = evaluator or Evaluator(corpus, category, self.assoc)
        self.ngrams, self.lines = self.evaluator.ngrams, self.evaluator.lines
        self._build_rhyme_families()
        self._learn_quatrain_schemes()
        self.fv_lengths = [len(tl) for p in corpus.of_category("free_verse") for tl in p.token_lines] or [6]
        self.imagery: set = set()

    # ------------------------------------------------------------ preparation
    def _eligible(self, w: str) -> bool:
        return (w.isalpha() and len(w) >= 3 and w not in STOPWORDS and in_dictionary(w)
                and syllables(w) <= 3 and self.model.has_predecessor(w))

    def _end_weight(self, w: str) -> float:
        return 1.0 + 3.0 * self.model.ends.get(w, 0.0) / max(1.0, self.model.total_starts) * 100 \
            + 0.05 * self.model.word_count[w]

    def _build_rhyme_families(self):
        fam: Dict[str, List[str]] = {}
        for w in self.model.word_count:
            if self._eligible(w):
                fam.setdefault(rhyme_key(w), []).append(w)
        self.families = {k: ws for k, ws in fam.items() if len(ws) >= 2}
        self.end_words = [w for w in self.model.word_count if self._eligible(w)]

    def _learn_quatrain_schemes(self):
        """Rhyme schemes of 4-line stanzas in the inspiring set (learned, not assumed)."""
        c: Counter = Counter()
        for p in self.corpus.of_category("quatrain"):
            for s in p.stanzas:
                ends = [t[-1] for t in (tokenize(l) for l in s) if t]
                if len(s) != 4 or len(ends) != 4:
                    continue
                scheme = ""
                for i, e in enumerate(ends):
                    j = next((j for j in range(i) if is_rhyme(ends[j], e)), None)
                    scheme += scheme[j] if j is not None else chr(65 + len(set(scheme)))
                c[scheme] += 1
        keep = {s: n for s, n in c.items() if len(set(s)) <= 3 and n >= 3}
        self.quatrain_schemes = keep or {"ABAB": 1, "AABB": 1, "ABCB": 1}

    # --------------------------------------------------------------- scoring
    def _local_score(self, tl: List[str], template: Optional[str], boost, target_len=None,
                     prev: Optional[List[str]] = None) -> float:
        ev, a = self.evaluator, self.assoc
        content = [w for w in tl if w not in STOPWORDS]
        theme = sum(w in boost for w in content) / len(content) if content else 0.0
        score = (0.15 * ev.line_typicality(tl) + 0.30 * ev.syntax_score([tl])
                 + 0.10 * clip(self.model.start_p(tl[0]) * 40) + 0.10 * theme)
        if content:                                   # can be concrete images or theme words
            score += 0.10 * clip(3 * sum(w in self.imagery for w in content) / len(content))
        if prev:                                   # STEP 2: does this line follow the previous one?
            score += 0.35 * clip(a.cosine(a.line_vector(tl), a.line_vector(prev)) / ev.coh_ref)
        if template is not None:
            score += 0.25 * meter_fit(tl, template)
        elif target_len:
            score += 0.25 * (1 - min(1.0, abs(len(tl) - target_len) / target_len))
        return score

    def _valid(self, tl: List[str], used_lines: set) -> bool:
        if len(tl) < 2 or tuple(tl) in self.lines or tuple(tl) in used_lines:
            return False
        if any(a == b for a, b in zip(tl, tl[1:])):
            return False
        if any(tl.count(w) > 1 and w not in STOPWORDS for w in set(tl)):
            return False
        n = self.cfg.max_copy_ngram
        return not (n in self.ngrams and any(tuple(tl[i:i + n]) in self.ngrams[n]
                                             for i in range(len(tl) - n + 1)))

    def _choose(self, scored: List[Tuple[float, List[str]]]) -> Optional[List[str]]:
        if not scored:
            return None
        top = sorted(scored, key=lambda x: -x[0])[:3]
        return self.rng.choices([t for _, t in top], weights=[3, 2, 1][:len(top)])[0]

    def _best_of(self, make, used_lines: set, score) -> Optional[List[str]]:
        """Collect valid candidates from `make()`, score them, pick among the best."""
        pool, tries = [], 0
        while len(pool) < self.cfg.line_pool and tries < max(40, self.cfg.line_pool * 6):
            tries += 1
            tl = make()
            if tl and self._valid(tl, used_lines):
                pool.append((score(tl), tl))
        return self._choose(pool)

    # ------------------------------------------------------------ line walkers
    def _walk_back(self, end_word: str, target: int, boost) -> Optional[List[str]]:
        words, syl = [end_word], syllables(end_word)
        if syl > target:
            return None
        ctx = (EOS, end_word)
        while syl < target:
            r = target - syl

            def wf(x, r=r):
                if x in (BOS, EOS) or syllables(x) > r:
                    return 0.0
                m = boost.get(x, 1.0)
                if syllables(x) == r:               # this word would start the line
                    sp = self.model.start_p(x)
                    m *= (1 + 30 * sp) if sp > 0 else 0.15
                return m

            nxt = self.model.sample("b", ctx, self.rng, wf)
            if nxt is None:
                return None
            words.append(nxt)
            syl += syllables(nxt)
            ctx = (ctx[1], nxt)
            if len(words) > MAX_WORDS:
                return None
        return words[::-1]

    def _walk_forward(self, boost) -> List[str]:
        words, ctx = [], (BOS, BOS)
        while True:
            n = len(words)

            def wf(x, n=n):
                if x == BOS:
                    return 0.0
                if x == EOS:
                    return 0.0 if n < 3 else (1e6 if n >= MAX_WORDS else 1.0)
                return boost.get(x, 1.0)

            nxt = self.model.sample("f", ctx, self.rng, wf)
            if nxt is None or nxt == EOS:
                return words
            words.append(nxt)
            ctx = (ctx[1], nxt)

    # ----------------------------------------------------------- rhyme planning
    def _pick_words(self, size: int, used_keys: set, used_words: set, boost) -> Optional[List[str]]:
        w8 = lambda w: self._end_weight(w) * boost.get(w, 1.0) * (2.0 if w in self.imagery else 1.0)  # noqa: E731
        if size == 1:
            ws = [w for w in self.end_words if w not in used_words]
            return [self.rng.choices(ws, weights=[w8(w) for w in ws])[0]] if ws else None
        keys = [k for k, ws in self.families.items() if k not in used_keys
                and len([w for w in ws if w not in used_words]) >= size]
        if not keys:
            return None
        key = self.rng.choices(keys, weights=[sum(w8(w) for w in self.families[k]) for k in keys])[0]
        pool = [w for w in self.families[key] if w not in used_words]
        chosen: List[str] = []
        while len(chosen) < size and pool:
            ok = [w for w in pool if all(is_rhyme(w, c) for c in chosen)]
            if not ok:
                return None
            w = self.rng.choices(ok, weights=[w8(x) for x in ok])[0]
            chosen.append(w)
            pool.remove(w)
        return chosen if len(chosen) == size else None

    def _pick_end_words(self, scheme: str, boosts, used_words: set) -> Optional[List[str]]:
        """One end word per line; lines with the same rhyme letter get one rhyme family."""
        ends: List[Optional[str]] = [None] * len(scheme)
        keys: set = set()
        taken = set(used_words)
        for letter in dict.fromkeys(scheme):
            pos = [i for i, c in enumerate(scheme) if c == letter]
            words = self._pick_words(len(pos), keys, taken, boosts[pos[0]])
            if not words:
                return None
            for i, w in zip(pos, words):
                ends[i] = w
            taken.update(words)
            if len(pos) > 1:
                keys.add(rhyme_key(words[0]))
        return ends  # type: ignore[return-value]

    def _build_scheme(self, scheme: str, syl: List[int], kind: str, boosts, used_words: set,
                      used_lines: set) -> Optional[List[List[str]]]:
        """One rhymed block (a stanza, or the whole sonnet): end words first, then lines in order."""
        for _ in range(self.cfg.group_retries):
            ends = self._pick_end_words(scheme, boosts, used_words)
            if ends is None:
                continue
            lines, prev, seen = [], None, set(used_lines)
            for i, w in enumerate(ends):
                tmpl = meter_template(syl[i], kind)
                tl = self._best_of(lambda: self._walk_back(w, syl[i], boosts[i]), seen,
                                   lambda t: self._local_score(t, tmpl, boosts[i], None, prev))
                if tl is None:
                    break
                lines.append(tl)
                seen.add(tuple(tl))
                prev = tl
            else:
                used_words.update(ends)
                used_lines.update(seen)
                return lines
        return None

    # ------------------------------------------------------------ rendering
    def _render(self, tl: List[str], end_of_stanza: bool) -> str:
        words = ["I" + w[1:] if (w == "i" or w.startswith("i'")) else ("O" if w == "o" else w) for w in tl]
        s = " ".join(words)
        s = s[0].upper() + s[1:]
        if end_of_stanza:
            return s + self.rng.choices([".", "!", "?"], weights=[8, 1, 1])[0]
        return s + self.rng.choices([",", ";", ""], weights=[6, 1, 3])[0]

    def _poem_from_lines(self, blocks, theme: str, meta: dict) -> Poem:
        stanzas = [[self._render(tl, i == len(b) - 1) for i, tl in enumerate(b)] for b in blocks]
        return Poem(self.category, stanzas, theme=theme, meta=meta)

    # --------------------------------------------------------------- one poem
    def generate_poem(self, plan: Optional[Plan] = None) -> Optional[Poem]:
        plan = plan or make_plan(self.rng, self.assoc, "short", self.category)
        assert plan.form == self.category, "plan form must match the generator category"
        self.imagery = set(plan.imagery)
        sizes = plan.block_sizes()
        boosts = [role_boost(plan, r, self.assoc) for r in outline(len(sizes))]
        used_words: set = set()
        used_lines: set = set()
        meta = {"idea": plan.idea, **plan.moods}
        blocks: List[List[List[str]]] = []

        if self.category == "free_verse":
            prev = None
            for size, b in zip(sizes, boosts):
                blk = []
                for _ in range(size):
                    n = self.rng.choice(self.fv_lengths)
                    tl = self._best_of(lambda: self._walk_forward(b), used_lines,
                                       lambda t: self._local_score(t, None, b, n, prev))
                    if tl is None:
                        return None
                    used_lines.add(tuple(tl))
                    blk.append(tl)
                    prev = tl
                blocks.append(blk)
        elif self.category == "sonnet":
            per_line = [b for sz, b in zip(sizes, boosts) for _ in range(sz)]
            lines = self._build_scheme(SONNET_SCHEME, [10] * 14, "iambic", per_line, used_words, used_lines)
            if lines is None:
                return None
            cuts = (0,) + SONNET_BREAKS + (14,)
            blocks = [lines[a:b] for a, b in zip(cuts, cuts[1:])]
            meta.update(scheme=SONNET_SCHEME, syllables=10)
        else:  # quatrain: one syllable pattern for the whole poem, one rhyme scheme per stanza
            sy, kind, _ = self.rng.choices(QUATRAIN_PATTERNS, weights=[p[2] for p in QUATRAIN_PATTERNS])[0]
            schemes = []
            for b in boosts:
                scheme = self.rng.choices(list(self.quatrain_schemes),
                                          weights=list(self.quatrain_schemes.values()))[0]
                lines = self._build_scheme(scheme, list(sy), kind, [b] * 4, used_words, used_lines)
                if lines is None:
                    return None
                blocks.append(lines)
                schemes.append(scheme)
            meta.update(scheme=",".join(schemes), syllables=",".join(map(str, sy)), meter=kind)
        return self._poem_from_lines(blocks, plan.theme[0], meta)

    # --------------------------------------------- generate many, then rank
    def generate(self, top_k: int = 3, plan: Optional[Plan] = None, length: str = "short",
                 pool: Optional[int] = None, rounds: int = 3):
        """One plan; generate in rounds until `top_k` poems pass stop_check (or rounds run out)."""
        plan = plan or make_plan(self.rng, self.assoc, length, self.category)
        scored = []
        for _ in range(rounds):
            for _ in range(pool or self.cfg.poem_pool):
                p = self.generate_poem(plan)
                if p is None:
                    continue
                m = self.evaluator.evaluate(p)
                checks = stop_check(p, plan, m)
                m.update(checks_passed=sum(checks.values()), stop_ok=float(all(checks.values())))
                scored.append((p, m))
            if sum(m["stop_ok"] for _, m in scored) >= top_k:
                break
        scored.sort(key=lambda x: (-x[1]["stop_ok"], -x[1]["fitness"]))
        return scored[:top_k]

    # -------------------------------------------------------------- baseline
    def baseline_poem(self, plan: Plan) -> Poem:
        """Plain Markov chain with the same shape as the plan: no rhyme, no meter, no ranking."""
        stanzas = []
        for sz in plan.block_sizes():
            st = []
            for i in range(sz):
                words, ctx = [], (BOS, BOS)
                while len(words) < MAX_WORDS:
                    nxt = self.model.sample("f", ctx, self.rng)
                    if nxt is None or nxt == EOS:
                        break
                    if nxt != BOS:
                        words.append(nxt)
                        ctx = (ctx[1], nxt)
                st.append(self._render(words or ["silence"], i == sz - 1))
            stanzas.append(st)
        return Poem(self.category, stanzas, meta={"baseline": True})
