"""Design planner premise, temperament, form, outline

The planner gives each stanza a role (introduction, development, complication, reversal, ending)
and a set of words to emphasise (theme, counter-theme, imagery).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional
from lm import STOPWORDS
from metrics import DANGLING
from phonetics import tokenize

# Words not in the corpus are filtered out automatically (see `known`).
PREMISES = [
    dict(idea="Being oneself is hard when several selves compete for the name.",
         theme=["name", "myself", "heart", "eyes"], counter=["nobody", "alone", "silence"]),
    dict(idea="Time is a creditor: we spend our days and still owe.",
         theme=["time", "spending", "account", "pay"], counter=["love", "stars", "night"]),
    dict(idea="The more we measure the world, the less of it we see.",
         theme=["proofs", "figures", "charts", "astronomer"], counter=["stars", "silence", "night"]),
    dict(idea="Death is the politest guest: he stops for you, uninvited.",
         theme=["death", "house", "door", "kindly"], counter=["sun", "day", "children"]),
]
MOODS = dict(                 # stored now, used for scoring in a later step
    atmosphere=["melancholic", "playful", "cynical", "romantic", "detached"],
    intellect=["philosophical", "paradoxical", "observational", "absurdist"],
    humour=["dry", "satirical", "self-deprecating", "surreal", "wordplay"],
    ending=["punchline", "paradox", "revelation", "ambiguity", "emotional reversal"],
)
IMAGERY = dict(
    dreamlike=["dream", "dreams", "sleep", "silent", "silence", "moon", "night", "dark", "darkness", "shade"],
    domestic=["house", "houses", "door", "roof", "bed", "garden", "table", "candle", "hearth", "window", "bench"],
    classical=["god", "gold", "heaven", "apollo", "homer", "pagan", "triton", "proteus", "saints", "temples", "bards"],
    urban=["city", "street", "streets", "ships", "crowds", "towers", "domes", "bridge", "harbor", "steamboat"],
    cosmic=["stars", "star", "sun", "sky", "skies", "moon", "heaven", "planet", "spheres", "space"],
)
LENGTHS = {"short": (8, 16), "medium": (16, 32), "long": (32, 40)}


@dataclass
class Plan:
    idea: str
    theme: List[str]
    counter: List[str]
    form: str
    n_lines: int
    imagery: List[str]
    moods: Dict[str, str]

    def block_sizes(self) -> List[int]:
        """Lines per stanza. Sonnet = 4+4+4+2; otherwise stanzas of 4."""
        if self.form == "sonnet":
            return [4, 4, 4, 2]
        q, r = divmod(self.n_lines, 4)
        return [4] * q + ([r] if r else [])


def outline(k: int) -> List[str]:
    """Role per stanza: introduction first, then reversal + ending last;
    the middle alternates development / complication."""
    if k <= 2:
        return ["introduction", "ending"][-k:]
    return ["introduction"] + [("development", "complication")[i % 2] for i in range(k - 3)] \
        + ["reversal", "ending"]


def make_plan(rng: random.Random, assoc, length: str = "short", form: Optional[str] = None) -> Plan:
    lo, hi = LENGTHS[length]
    form = form or rng.choice(["quatrain", "free_verse"] + (["sonnet"] if length == "short" else []))
    n = 14 if form == "sonnet" else rng.randint(lo, hi)
    if form == "quatrain":
        n = n // 4 * 4                                    # whole stanzas only
    known = lambda ws: [w for w in ws if w in assoc.count]          # noqa: E731
    p = rng.choice(PREMISES)
    theme = known(p["theme"]) or [rng.choice(sorted(assoc.candidate_themes()))]
    style = rng.choice(list(IMAGERY))
    return Plan(p["idea"], theme, known(p["counter"]), form, n, known(IMAGERY[style]),
                {**{k: rng.choice(v) for k, v in MOODS.items()}, "imagery": style})


def role_boost(plan: Plan, role: str, assoc) -> Dict[str, float]:
    """Word multipliers for one stanza: the role decides which words are pushed."""
    words = {"reversal": plan.counter or plan.theme,
             "ending": plan.theme + plan.counter}.get(role, plan.theme)
    boost: Dict[str, float] = {}
    for w in words:
        for k, v in assoc.theme_boost(w).items():
            boost[k] = max(boost.get(k, 1.0), v)
    for w in plan.imagery:                                # imagery stays on throughout
        boost[w] = max(boost.get(w, 1.0), 3.0)
    return boost


def _content(lines):
    return {w for l in lines for w in tokenize(l) if w not in STOPWORDS}


def stop_check(poem, plan, m) -> Dict[str, bool]:
    """A poem is finished only if all four checks pass."""
    first, last = _content(poem.stanzas[0]), _content(poem.stanzas[-1])
    plan_words = set(plan.theme) | set(plan.counter)
    return dict(
        length=len(poem.lines) == sum(plan.block_sizes()),
        idea=len(_content(poem.lines) & plan_words) >= min(2, len(plan_words)),
        ending=tokenize(poem.lines[-1])[-1] not in DANGLING
        and len(first & last) / max(1, len(first | last)) < 0.5,
        coherence=m["cohesion"] >= 0.3 and m["adjacent_repeats"] == 0,
        imagery=len(_content(poem.lines) & set(plan.imagery)) >= min(3, len(plan.imagery))
        and sum(bool(_content(s) & set(plan.imagery)) for s in poem.stanzas) * 2 >= len(poem.stanzas),
    )
