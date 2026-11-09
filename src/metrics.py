"""Poem quality evaluation.

The evaluation is the centre of this project: the generator is a simple
(Markov chain + constraints) method, so what matters is how good the poems
actually are. Quality is reported as a PROFILE of components, not just one
number:

  form        rhyme, syllable regularity, meter           (rhymed forms only)
  typicality  how much it looks like the category         (Ritchie's 'typ')
  novelty     how far it is from the inspiring set        (Ritchie's novelty)
  cohesion    do neighbouring lines share a topic
  fluency     surface sanity: dangling endings, repeats, line starters

Typicality and cohesion are CALIBRATED on the real poems of the category
(leave-one-poem-out), so 'typical enough' is learned from the inspiring
set instead of being an arbitrary threshold.
"""
from __future__ import annotations

import statistics
from typing import Dict, List, Optional

from lm import Associations, Corpus, MarkovModel, NgramLM, Poem, STOPWORDS, BOS
from phonetics import (best_meter_fit, is_rhyme, line_syllables, meter_fit,
                       meter_template, tokenize)

SONNET_SCHEME = "ABABCDCDEFEFGG"
SONNET_BREAKS = (4, 8, 12)               # stanza breaks when printing a sonnet
DANGLING = set("""the a an of to and or but in on with for my thy his her their our your that which who is was
are were am be by at as if""".split())

# Weights of the aggregate quality score Q (components are all in 0..1).
W_RHYMED = dict(form=0.35, typicality=0.25, fluency=0.20, cohesion=0.20)
W_FREE = dict(typicality=0.40, fluency=0.35, cohesion=0.25)
W_FORM = dict(rhyme=0.40, syllable=0.25, meter=0.35)
NOVELTY_FLOOR = 0.6                      # F = Q * (0.6 + 0.4 * N)


def clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def percentile(xs: List[float], q: float) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


class Evaluator:
    def __init__(self, corpus: Corpus, category: str, assoc: Optional[Associations] = None,
                 model: Optional[MarkovModel] = None):
        self.corpus, self.category = corpus, category
        self.assoc = assoc or Associations(corpus)
        self.V = len(corpus.vocab)
        cat_poems = corpus.of_category(category)
        self.lm = NgramLM(self.V).fit([tl for p in cat_poems for tl in p.token_lines])
        self.ngrams = corpus.line_ngram_sets(6)
        self.lines = corpus.line_set()
        self.starters = {w for p in corpus.poems for tl in p.token_lines for w in tl[:1]}
        self._calibrate()

    # -------------------------------------------------- calibration on real poems
    def _calibrate(self):
        units = self.corpus.reference_units(self.category)
        typ_by, syn = {}, []
        other = [tl for p in self.corpus.poems if p.category != self.category for tl in p.token_lines]
        self.rest_lm = NgramLM(self.V).fit(other)
        self.syn_lm = NgramLM(len(STOPWORDS) + 1).fit(
            [self._classes(tl) for p in self.corpus.poems for tl in p.token_lines])
        for i in {u.source_idx for u in units}:
            mine = [tl for p in self.corpus.of_category(self.category) if p.source_idx != i
                    for tl in p.token_lines]
            lm = NgramLM(self.V).fit(mine)
            slm = NgramLM(len(STOPWORDS) + 1).fit(
                [self._classes(tl) for p in self.corpus.poems if p.source_idx != i
                 for tl in p.token_lines])
            for k, u in enumerate(units):
                if u.source_idx == i:
                    typ_by[k] = lm.mean_logprob(u.token_lines) - self.rest_lm.mean_logprob(u.token_lines)
                    syn.append(slm.mean_logprob([self._classes(t) for t in u.token_lines]))
        # TYPICALITY = category-vs-rest log-likelihood ratio (how much more it looks
        # like THIS category than like the others). 0 = no preference. The threshold
        # for 'typical enough' is learned: the 25th-percentile real poem of the
        # category (leave-one-poem-out). Reaching it gives full marks (Ritchie's
        # threshold idea, but data-driven instead of arbitrary).
        typ = [typ_by[k] for k in range(len(units))]
        self.ref_units, self.typ_ref = units, typ      # typ_ref is aligned with ref_units
        self.typ_low, self.typ_med = 0.0, percentile(typ, 0.50)
        self.typ_high = max(percentile(typ, 0.25), 0.05)
        self.f_mu, self.f_sd = self._stats([self._feats(u.token_lines) for u in units])
        self.l_mu, self.l_sd = self._stats([self._line_feats(t) for u in units for t in u.token_lines])
        # Syntax / cohesion: 0 = 10th-percentile real poem, 1 = 90th.
        self.syn_low, self.syn_high = percentile(syn, 0.10), percentile(syn, 0.90)
        coh = [self._cohesion_raw(u.token_lines) for u in units]
        self.coh_low, self.coh_ref = percentile(coh, 0.10), max(percentile(coh, 0.90), 1e-6)

    # ---- feature-based typicality: z-scores against the real poems of the category
    @staticmethod
    def _feats(tls: List[List[str]]) -> List[float]:
        words = [w for t in tls for w in t]
        n, nw = max(1, len(tls)), max(1, len(words))
        wpl = [len(t) for t in tls] or [0]
        mean_w = sum(wpl) / len(wpl)
        sd_w = (sum((x - mean_w) ** 2 for x in wpl) / len(wpl)) ** 0.5
        return [mean_w, sd_w, sum(line_syllables(t) for t in tls) / n,
                sum(w in STOPWORDS for w in words) / nw, sum(len(w) for w in words) / nw,
                len(set(words)) / nw]

    @staticmethod
    def _line_feats(tl: List[str]) -> List[float]:
        nw = max(1, len(tl))
        return [len(tl), line_syllables(tl), sum(w in STOPWORDS for w in tl) / nw,
                sum(len(w) for w in tl) / nw]

    @staticmethod
    def _stats(rows: List[List[float]]):
        cols = list(zip(*rows))
        mu = [statistics.mean(c) for c in cols]
        sd = [max(statistics.pstdev(c), 0.08 * abs(m), 1e-3) for c, m in zip(cols, mu)]
        return mu, sd

    @staticmethod
    def _zdist(x: List[float], mu, sd) -> float:
        return sum(abs((a - m) / s) for a, m, s in zip(x, mu, sd)) / len(x)

    @staticmethod
    def _dist_to_score(d: float) -> float:
        # a real poem sits ~0.8 sd from the centre on average -> full marks up to 0.8
        return clip(1 - max(0.0, d - 0.8) / 1.6)

    def feature_typicality(self, tls: List[List[str]]) -> float:
        return self._dist_to_score(self._zdist(self._feats(tls), self.f_mu, self.f_sd))

    def line_typicality(self, tl: List[str]) -> float:
        return self._dist_to_score(self._zdist(self._line_feats(tl), self.l_mu, self.l_sd))

    @staticmethod
    def _classes(tl: List[str]) -> List[str]:
        """Function words stay literal, every content word becomes 'C'. A class
        bigram model over this captures rough syntax ('the C of the C')."""
        return [w if w in STOPWORDS else "C" for w in tl]

    def llr(self, token_lines: List[List[str]]) -> float:
        return self.lm.mean_logprob(token_lines) - self.rest_lm.mean_logprob(token_lines)

    def typicality_score(self, raw: float) -> float:
        return clip((raw - self.typ_low) / (self.typ_high - self.typ_low))

    def syntax_score(self, token_lines: List[List[str]]) -> float:
        raw = self.syn_lm.mean_logprob([self._classes(t) for t in token_lines])
        return clip((raw - self.syn_low) / (self.syn_high - self.syn_low))

    # --------------------------------------------------------------- components
    def _rhyme(self, poem: Poem) -> Optional[float]:
        if self.category == "free_verse":
            return None
        if self.category == "sonnet":
            ends = [t[-1] for t in poem.token_lines]
            if len(ends) != 14:
                return 0.0
            pairs = [(0, 2), (1, 3), (4, 6), (5, 7), (8, 10), (9, 11), (12, 13)]
            return sum(is_rhyme(ends[a], ends[b]) for a, b in pairs) / len(pairs)
        scores = []                                          # quatrain: per stanza
        for s in poem.stanzas:
            ends = [t[-1] for t in (tokenize(l) for l in s) if t]
            with_partner = sum(any(is_rhyme(e, o) for j, o in enumerate(ends) if j != i)
                               for i, e in enumerate(ends))
            scores.append(clip(with_partner / 2))            # >=1 rhyming pair is full marks
        return sum(scores) / len(scores) if scores else 0.0

    def _syllable(self, poem: Poem) -> Optional[float]:
        """Sonnet: lines should have 10 syllables. Quatrain: each stanza should be
        regular, either one length throughout (8,8,8,8) or alternating (8,6,8,6)."""
        if self.category == "free_verse":
            return None
        close = lambda s, t: 1 - min(1, abs(s - t) / 3)          # noqa: E731
        if self.category == "sonnet":
            sy = [line_syllables(t) for t in poem.token_lines]
            return sum(close(s, 10) for s in sy) / len(sy) if sy else 0.0
        scores = []
        for st in poem.stanzas:
            sy = [line_syllables(t) for t in (tokenize(l) for l in st) if t]
            if not sy:
                continue
            flat = statistics.mode(sy)
            alt = [statistics.mode(sy[0::2]), statistics.mode(sy[1::2] or sy)]
            a = sum(close(s, flat) for s in sy) / len(sy)
            b = sum(close(s, alt[i % 2]) for i, s in enumerate(sy)) / len(sy)
            scores.append(max(a, b))
        return sum(scores) / len(scores) if scores else 0.0

    def _meter(self, poem: Poem) -> Optional[float]:
        if self.category == "free_verse":
            return None
        kinds = ("iambic",) if self.category == "sonnet" else ("iambic", "trochaic")
        fits = []
        for t in poem.token_lines:
            n = line_syllables(t)
            fits.append(max(meter_fit(t, meter_template(n, k)) for k in kinds))
        return sum(fits) / len(fits) if fits else 0.0

    def _cohesion_raw(self, token_lines: List[List[str]]) -> float:
        vecs = [self.assoc.line_vector(t) for t in token_lines]
        sims = [self.assoc.cosine(vecs[i], vecs[j]) for i in range(len(vecs))
                for j in (i + 1, i + 2) if j < len(vecs)]
        return sum(sims) / len(sims) if sims else 0.0

    def _fluency(self, poem: Poem) -> Dict[str, float]:
        tls = poem.token_lines
        n = max(1, len(tls))
        dangling = sum(t[-1] in DANGLING for t in tls) / n
        dup = sum(any(a == b for a, b in zip(t, t[1:])) for t in tls) / n
        dup_lines = 1 - len({tuple(t) for t in tls}) / n
        starter_ok = sum(t[0] in self.starters for t in tls) / n
        surface = clip(1 - 0.45 * dangling - 0.25 * dup - 0.15 * dup_lines - 0.15 * (1 - starter_ok))
        syntax = self.syntax_score(tls)
        flu = 0.5 * syntax + 0.5 * surface
        return dict(fluency=flu, syntax=syntax, surface=surface, dangling=dangling,
                    adjacent_repeats=dup, starter_ok=starter_ok)

    def novelty(self, poem: Poem) -> Dict[str, float]:
        """Distance to the inspiring set (whole corpus)."""
        tls = poem.token_lines
        tri = [tuple(t[i:i + 3]) for t in tls for i in range(len(t) - 2)]
        tri_nov = sum(g not in self.ngrams[3] for g in tri) / len(tri) if tri else 1.0
        covered = total = 0
        for t in tls:                                   # words inside a copied >=4-gram
            mark = [False] * len(t)
            for i in range(len(t) - 3):
                if tuple(t[i:i + 4]) in self.ngrams[4]:
                    for k in range(i, i + 4):
                        mark[k] = True
            covered += sum(mark)
            total += len(t)
        copy_ratio = covered / total if total else 0.0
        exact = sum(tuple(t) in self.lines for t in tls) / max(1, len(tls))
        return dict(novelty=0.5 * tri_nov + 0.5 * (1 - copy_ratio), trigram_novelty=tri_nov,
                    copy_ratio=copy_ratio, exact_line_copies=exact)

    # ------------------------------------------------------------------ public
    def evaluate(self, poem: Poem, with_novelty: bool = True) -> Dict[str, float]:
        m: Dict[str, float] = {}
        rhyme, syl, met = self._rhyme(poem), self._syllable(poem), self._meter(poem)
        if rhyme is not None:
            m.update(rhyme=rhyme, syllable=syl, meter=met)
            m["form"] = sum(W_FORM[k] * m[k] for k in W_FORM)
        m["category_llr"] = self.llr(poem.token_lines)       # reported, weak with this little data
        m["typicality"] = self.feature_typicality(poem.token_lines)
        coh_raw = self._cohesion_raw(poem.token_lines)
        m["cohesion_raw"] = coh_raw
        m["cohesion"] = clip((coh_raw - self.coh_low) / (self.coh_ref - self.coh_low))
        m.update(self._fluency(poem))
        w = W_FREE if self.category == "free_verse" else W_RHYMED
        m["quality"] = sum(w[k] * m[k] for k in w)
        if with_novelty:
            m.update(self.novelty(poem))
            m["fitness"] = m["quality"] * (NOVELTY_FLOOR + (1 - NOVELTY_FLOOR) * m["novelty"])
        if poem.theme:
            nb = set(self.assoc.neighbours(poem.theme)) | {poem.theme}
            cw = [w_ for t in poem.token_lines for w_ in t if w_ not in STOPWORDS]
            m["theme_fit"] = sum(x in nb for x in cw) / len(cw) if cw else 0.0
        return m


def diversity(poems: List[Poem]) -> float:
    """Mean pairwise Jaccard distance between the word sets of poems (0 = all identical)."""
    sets = [{w for t in p.token_lines for w in t} for p in poems]
    d, n = 0.0, 0
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            u = len(sets[i] | sets[j])
            d += 1 - (len(sets[i] & sets[j]) / u if u else 1.0)
            n += 1
    return d / n if n else 0.0


def summarise(rows: List[Dict[str, float]]) -> Dict[str, tuple]:
    keys = sorted({k for r in rows for k in r})
    out = {}
    for k in keys:
        xs = [r[k] for r in rows if k in r and r[k] is not None]
        if xs:
            out[k] = (statistics.mean(xs), statistics.pstdev(xs))
    return out


def cohens_d(a: List[float], b: List[float]) -> float:
    if len(a) < 2 or len(b) < 2:
        return 0.0
    sp = ((statistics.pvariance(a) + statistics.pvariance(b)) / 2) ** 0.5
    return (statistics.mean(a) - statistics.mean(b)) / sp if sp else 0.0
