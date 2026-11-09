"""Poem generator: Markov chains + rhyme/meter constraints + generate-and-rank.

How a rhymed poem (quatrain / sonnet) is built
  1. Plan the form: rhyme scheme and syllables per line. Quatrain schemes
     are sampled from the schemes found in the inspiring set's stanzas.
  2. Pick a theme word; words associated with it are boosted while sampling.
  3. For every rhyme letter, pick a rhyme family (words sharing their final
     sounds, from the CMU dictionary) and one end word per line.
  4. Build each line BACKWARDS from its end word with the reverse Markov
     chain until the syllable count is exact. Rhyme and length are therefore
     satisfied by construction, not by hoping.
  5. For each line, sample a pool of valid candidates and choose among the
     best by a local score (meter, language-model typicality, line starter,
     theme, novelty).
  6. Repeat for several whole poems and rank them with the full evaluator.
Free verse has no rhyme or meter, so lines are sampled forwards.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from lm import Associations, Corpus, MarkovModel, Poem, BOS, EOS, STOPWORDS
from metrics import Evaluator, SONNET_BREAKS, SONNET_SCHEME, clip
from phonetics import (is_rhyme, line_syllables, meter_fit, meter_template,
                       rhyme_key, in_dictionary, syllables, best_meter_fit)

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
    group_retries: int = 25          # re-picks of a rhyme group that fails to build
    max_copy_ngram: int = 5          # reject lines containing a copied n-gram this long
    free_verse_lines: int = 8


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
        self.ngrams = self.evaluator.ngrams
        self.lines = self.evaluator.lines
        self.themes = sorted(self.assoc.candidate_themes())
        self._build_rhyme_families()
        self._learn_quatrain_schemes()
        fv = [len(tl) for p in corpus.of_category("free_verse") for tl in p.token_lines]
        self.fv_lengths = fv or [6]

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
        from collections import Counter
        from phonetics import tokenize
        c: Counter = Counter()
        for p in self.corpus.of_category("quatrain"):
            for s in p.stanzas:
                if len(s) != 4:
                    continue
                ends = [t[-1] for t in (tokenize(l) for l in s) if t]
                if len(ends) != 4:
                    continue
                names, scheme = {}, ""
                for i, e in enumerate(ends):
                    for j in range(i):
                        if is_rhyme(ends[j], e):
                            scheme += scheme[j]
                            break
                    else:
                        scheme += chr(65 + len(set(scheme)))
                        names[e] = scheme[-1]
                c[scheme] += 1
        keep = {s: n for s, n in c.items() if len(s) == 4 and len(set(s)) <= 3 and len(set(s)) < 4
                and n >= 3 and s != "ABCD"}
        self.quatrain_schemes = keep or {"ABAB": 1, "AABB": 1, "ABCB": 1}
        self.scheme_counts = dict(c)

    # --------------------------------------------------------------- scoring
    def _weight_fn(self, boost: Dict[str, float]):
        return lambda x: boost.get(x, 1.0)

    def _local_score(self, tl: List[str], template: Optional[str], boost, target_len=None) -> float:
        ev = self.evaluator
        lm_n = ev.line_typicality(tl)
        syn = ev.syntax_score([tl])
        start_n = clip(self.model.start_p(tl[0]) * 40)
        content = [w for w in tl if w not in STOPWORDS]
        theme = (sum(w in boost for w in content) / len(content)) if content else 0.0
        score = 0.25 * lm_n + 0.30 * syn + 0.10 * start_n + 0.10 * theme
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
        for w in set(tl):
            if tl.count(w) > 1 and w not in STOPWORDS:
                return False
        n = self.cfg.max_copy_ngram
        if n in self.ngrams and any(tuple(tl[i:i + n]) in self.ngrams[n] for i in range(len(tl) - n + 1)):
            return False
        return True

    def _choose(self, scored: List[Tuple[float, List[str]]]) -> Optional[List[str]]:
        if not scored:
            return None
        scored.sort(key=lambda x: -x[0])
        top = scored[:3]
        return self.rng.choices([t for _, t in top], weights=[3, 2, 1][:len(top)])[0]

    # ------------------------------------------------------------ line builders
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

    def _best_line_back(self, end_word, target, template, boost, used_lines) -> Optional[List[str]]:
        pool, tries = [], 0
        max_tries = max(40, self.cfg.line_pool * 6)
        while len(pool) < self.cfg.line_pool and tries < max_tries:
            tries += 1
            tl = self._walk_back(end_word, target, boost)
            if tl and self._valid(tl, used_lines):
                pool.append((self._local_score(tl, template, boost), tl))
                if self.cfg.line_pool == 1:
                    break
        return self._choose(pool)

    def _best_line_forward(self, boost, target_len, used_lines) -> Optional[List[str]]:
        pool, tries = [], 0
        max_tries = max(40, self.cfg.line_pool * 6)
        wf_base = self._weight_fn(boost)
        while len(pool) < self.cfg.line_pool and tries < max_tries:
            tries += 1
            words, ctx = [], (BOS, BOS)
            while True:
                n = len(words)

                def wf(x, n=n):
                    if x == EOS:
                        return 0.0 if n < 3 else (1e6 if n >= MAX_WORDS else 1.0)
                    return wf_base(x) if x != BOS else 0.0

                nxt = self.model.sample("f", ctx, self.rng, wf)
                if nxt is None or nxt == EOS:
                    break
                words.append(nxt)
                ctx = (ctx[1], nxt)
            if words and self._valid(words, used_lines):
                pool.append((self._local_score(words, None, boost, target_len), words))
                if self.cfg.line_pool == 1:
                    break
        return self._choose(pool)

    # ----------------------------------------------------------- rhyme groups
    def _pick_words(self, size: int, used_keys: set, used_words: set, boost) -> Optional[List[str]]:
        if size == 1:
            ws = [w for w in self.end_words if w not in used_words]
            wts = [self._end_weight(w) * boost.get(w, 1.0) for w in ws]
            return [self.rng.choices(ws, weights=wts)[0]]
        keys = [k for k, ws in self.families.items() if k not in used_keys
                and len([w for w in ws if w not in used_words]) >= size]
        if not keys:
            return None
        kw = [sum(self._end_weight(w) * boost.get(w, 1.0) for w in self.families[k]) for k in keys]
        key = self.rng.choices(keys, weights=kw)[0]
        pool = [w for w in self.families[key] if w not in used_words]
        chosen: List[str] = []
        while len(chosen) < size and pool:
            ok = [w for w in pool if all(is_rhyme(w, c) for c in chosen)]
            if not ok:
                return None
            w = self.rng.choices(ok, weights=[self._end_weight(x) * boost.get(x, 1.0) for x in ok])[0]
            chosen.append(w)
            pool.remove(w)
        return chosen if len(chosen) == size else None

    def _build_scheme(self, scheme: str, syl: List[int], kind: str, boost, used_words: set,
                      used_lines: set) -> Optional[List[List[str]]]:
        """Return token lines for one rhymed block (a stanza, or the whole sonnet)."""
        lines: List[Optional[List[str]]] = [None] * len(scheme)
        used_keys: set = set()
        for letter in dict.fromkeys(scheme):
            pos = [i for i, c in enumerate(scheme) if c == letter]
            done = False
            for _ in range(self.cfg.group_retries):
                words = self._pick_words(len(pos), used_keys, used_words, boost)
                if not words:
                    continue
                built = []
                for i, w in zip(pos, words):
                    tmpl = meter_template(syl[i], kind)
                    tl = self._best_line_back(w, syl[i], tmpl, boost, used_lines)
                    if tl is None:
                        break
                    built.append(tl)
                else:
                    for i, tl in zip(pos, built):
                        lines[i] = tl
                        used_lines.add(tuple(tl))
                    used_words.update(words)
                    if len(pos) > 1:
                        used_keys.add(rhyme_key(words[0]))
                    done = True
                    break
            if not done:
                return None
        return lines  # type: ignore[return-value]

    # ------------------------------------------------------------ rendering
    def _render(self, tl: List[str], last: bool, end_of_stanza: bool) -> str:
        words = []
        for w in tl:
            if w == "i" or w.startswith("i'"):
                w = "I" + w[1:]
            elif w == "o":
                w = "O"
            words.append(w)
        s = " ".join(words)
        s = s[0].upper() + s[1:]
        if end_of_stanza:
            return s + self.rng.choices([".", "!", "?"], weights=[8, 1, 1])[0]
        return s + self.rng.choices([",", ";", ""], weights=[6, 1, 3])[0]

    def _poem_from_lines(self, blocks: List[List[List[str]]], theme: str, meta: dict) -> Poem:
        stanzas = []
        for b in blocks:
            stanzas.append([self._render(tl, False, i == len(b) - 1) for i, tl in enumerate(b)])
        return Poem(self.category, stanzas, theme=theme, meta=meta)

    # --------------------------------------------------------------- one poem
    def generate_poem(self, theme: Optional[str] = None, n_stanzas: int = 1,
                      n_lines: Optional[int] = None) -> Optional[Poem]:
        if theme is None:
            theme = self.rng.choice(self.themes)
        boost = self.assoc.theme_boost(theme)
        used_words: set = set()
        used_lines: set = set()
        meta = {"theme": theme}
        if self.category == "free_verse":
            blocks = []
            for _ in range(n_lines or self.cfg.free_verse_lines):
                tl = self._best_line_forward(boost, self.rng.choice(self.fv_lengths), used_lines)
                if tl is None:
                    return None
                used_lines.add(tuple(tl))
                blocks.append(tl)
            return self._poem_from_lines([blocks], theme, meta)
        if self.category == "sonnet":
            lines = self._build_scheme(SONNET_SCHEME, [10] * 14, "iambic", boost, used_words, used_lines)
            if lines is None:
                return None
            cuts = (0,) + SONNET_BREAKS + (14,)
            blocks = [lines[a:b] for a, b in zip(cuts, cuts[1:])]
            meta.update(scheme=SONNET_SCHEME, syllables=10)
            return self._poem_from_lines(blocks, theme, meta)
        # quatrain
        pats = QUATRAIN_PATTERNS
        sy, kind, _ = self.rng.choices(pats, weights=[p[2] for p in pats])[0]
        blocks, schemes = [], []
        for _ in range(n_stanzas):
            scheme = self.rng.choices(list(self.quatrain_schemes), weights=list(self.quatrain_schemes.values()))[0]
            lines = self._build_scheme(scheme, list(sy), kind, boost, used_words, used_lines)
            if lines is None:
                return None
            blocks.append(lines)
            schemes.append(scheme)
        meta.update(scheme=",".join(schemes), syllables=",".join(map(str, sy)), meter=kind)
        return self._poem_from_lines(blocks, theme, meta)

    # --------------------------------------------- generate many, then rank
    def generate(self, top_k: int = 3, theme: Optional[str] = None, n_stanzas: int = 1,
                 n_lines: Optional[int] = None, pool: Optional[int] = None):
        """Generate `pool` poems, evaluate them all, return the best `top_k` as
        (poem, metrics) sorted by fitness."""
        pool = pool or self.cfg.poem_pool
        scored = []
        attempts = 0
        while len(scored) < pool and attempts < pool * 5:
            attempts += 1
            p = self.generate_poem(theme, n_stanzas, n_lines)
            if p is not None:
                scored.append((p, self.evaluator.evaluate(p)))
        scored.sort(key=lambda x: -x[1]["fitness"])
        return scored[:top_k]

    # -------------------------------------------------------------- baseline
    def baseline_poem(self, n_stanzas: int = 1, n_lines: Optional[int] = None) -> Poem:
        """Plain Markov chain: no rhyme, no meter, no filtering, no ranking."""
        if self.category == "sonnet":
            sizes = [4, 4, 4, 2]
        elif self.category == "quatrain":
            sizes = [4] * n_stanzas
        else:
            sizes = [n_lines or self.cfg.free_verse_lines]
        stanzas = []
        for sz in sizes:
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
                words = words or ["silence"]
                st.append(self._render(words, False, i == sz - 1))
            stanzas.append(st)
        return Poem(self.category, stanzas, meta={"baseline": True})
