"""Generate poems.

    python3 src/main.py --category sonnet --theme night --top 3 --seed 42
    python3 src/main.py --category all --top 2 --seed 1
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from generator import GenConfig, PoemGenerator          # noqa: E402
from lm import Associations, Corpus                       # noqa: E402
from metrics import Evaluator                             # noqa: E402

CATS = ["quatrain", "sonnet", "free_verse"]
SHOW = ["rhyme", "syllable", "meter", "typicality", "syntax", "cohesion", "fluency",
        "novelty", "quality", "fitness"]


def fmt_metrics(m):
    return "  ".join(f"{k}={m[k]:.2f}" for k in SHOW if k in m)


def main():
    here = os.path.dirname(__file__)
    ap = argparse.ArgumentParser(description="Markov-chain poem generator with rhyme/meter constraints")
    ap.add_argument("--data", default=os.path.join(here, "..", "data", "inspiring_set.json"))
    ap.add_argument("--category", default="all", choices=CATS + ["all"])
    ap.add_argument("--theme", default=None, help="a word from the corpus, e.g. night, love, sea")
    ap.add_argument("--top", type=int, default=3, help="poems to keep after ranking")
    ap.add_argument("--pool", type=int, default=12, help="poems generated before ranking")
    ap.add_argument("--stanzas", type=int, default=1, help="stanzas per quatrain poem")
    ap.add_argument("--lines", type=int, default=8, help="lines in a free-verse poem")
    ap.add_argument("--order2", type=float, default=0.6, help="trigram weight (lower = more novel)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--outdir", default=os.path.join(here, "..", "outputs"))
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    corpus = Corpus(a.data)
    assoc = Associations(corpus)
    print(f"Loaded {len(corpus.poems)} poems: " +
          ", ".join(f"{len(corpus.of_category(c))} {c}" for c in CATS))
    if a.theme and a.theme not in assoc.count:
        print(f"Theme '{a.theme}' is not a content word in the corpus; picking themes at random.")
        a.theme = None

    for cat in (CATS if a.category == "all" else [a.category]):
        ev = Evaluator(corpus, cat, assoc)
        gen = PoemGenerator(corpus, cat, GenConfig(order2_weight=a.order2, poem_pool=a.pool),
                            seed=a.seed, evaluator=ev)
        results = gen.generate(top_k=a.top, theme=a.theme, n_stanzas=a.stanzas, n_lines=a.lines)
        out = os.path.join(a.outdir, f"best_poems_{cat}.txt")
        with open(out, "w", encoding="utf-8") as f:
            for i, (p, m) in enumerate(results, 1):
                block = (f"[{cat} #{i}]  theme: {p.theme}  scheme: {p.meta.get('scheme', '-')}\n\n"
                         f"{p.text()}\n\n{fmt_metrics(m)}\n")
                print("\n" + "=" * 60 + "\n" + block)
                f.write(block + "\n" + "-" * 60 + "\n\n")
        print(f"(saved to {out})")


if __name__ == "__main__":
    main()
