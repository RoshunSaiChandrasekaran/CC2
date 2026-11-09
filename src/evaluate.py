"""Evaluation experiment: how good are the poems, and what do the constraints buy us?

Four conditions per category (same corpus, same metrics):
  real          the real poems of the inspiring set (reference / upper bound)
  baseline      plain Markov chain: no rhyme, no meter, no filtering, no ranking
  constrained   rhyme + meter + line filtering, but NO ranking (first valid candidates)
  full          the complete system (constraints + line scoring + poem ranking)

    python3 src/evaluate.py --n 40 --pool 10 --seed 7

Writes outputs/evaluation_summary.md, evaluation_poems.csv, evaluation_profile.png
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import matplotlib                                          # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                            # noqa: E402

from generator import GenConfig, PoemGenerator            # noqa: E402
from lm import Associations, Corpus                       # noqa: E402
from metrics import Evaluator, cohens_d, diversity, summarise   # noqa: E402

CATS = ["quatrain", "sonnet", "free_verse"]
PROFILE = ["rhyme", "syllable", "meter", "typicality", "syntax", "cohesion", "fluency", "novelty", "quality"]
TABLE = PROFILE + ["fitness"]
COND = ["real", "baseline", "constrained", "full"]
COLORS = {"real": "#7a7a7a", "baseline": "#c9a227", "constrained": "#3b7dd8", "full": "#1f9d6b"}


def run_category(corpus, assoc, cat, n, pool, seed):
    ev = Evaluator(corpus, cat, assoc)
    data = {}
    real = ev.ref_units
    data["real"] = (real, [ev.evaluate(u, with_novelty=False) for u in real])

    g = PoemGenerator(corpus, cat, GenConfig(), seed=seed, evaluator=ev)
    base = [g.baseline_poem() for _ in range(n)]
    data["baseline"] = (base, [ev.evaluate(p) for p in base])

    g = PoemGenerator(corpus, cat, GenConfig(line_pool=1), seed=seed + 1, evaluator=ev)
    cons = []
    while len(cons) < n:
        p = g.generate_poem()
        if p is not None:
            cons.append(p)
    data["constrained"] = (cons, [ev.evaluate(p) for p in cons])

    g = PoemGenerator(corpus, cat, GenConfig(), seed=seed + 2, evaluator=ev)
    full, fm = [], []
    for _ in range(n):
        (p, m), = g.generate(top_k=1, pool=pool)
        full.append(p)
        fm.append(m)
    data["full"] = (full, fm)
    return data


def main():
    here = os.path.dirname(__file__)
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(here, "..", "data", "inspiring_set.json"))
    ap.add_argument("--n", type=int, default=40, help="poems per condition per category")
    ap.add_argument("--pool", type=int, default=10, help="poems generated per ranked poem")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--outdir", default=os.path.join(here, "..", "outputs"))
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    corpus = Corpus(a.data)
    assoc = Associations(corpus)
    md = ["# Evaluation summary\n",
          f"{a.n} poems per condition per category (seed {a.seed}); mean (sd). All scores 0-1.\n",
          "`real` rows are the inspiring-set poems themselves (novelty not applicable).\n"]
    rows_csv, all_data = [], {}
    for cat in CATS:
        print(f"== {cat} ...", flush=True)
        data = run_category(corpus, assoc, cat, a.n, a.pool, a.seed)
        all_data[cat] = data
        keys = [k for k in TABLE if k in data["full"][1][0]]
        md.append(f"\n## {cat}\n")
        md.append("| condition | " + " | ".join(keys) + " |")
        md.append("|---|" + "---|" * len(keys))
        for c in COND:
            s = summarise(data[c][1])
            md.append(f"| {c} | " + " | ".join(
                f"{s[k][0]:.2f} ({s[k][1]:.2f})" if k in s else "-" for k in keys) + " |")
            for p, m in zip(*data[c]):
                rows_csv.append({"category": cat, "condition": c, "text": p.text().replace("\n", " / "), **m})
        q = lambda c: [m["quality"] for m in data[c][1]]      # noqa: E731
        md.append(f"\nEffect size on quality (Cohen's d): constrained vs baseline = "
                  f"{cohens_d(q('constrained'), q('baseline')):.2f}, "
                  f"full vs constrained = {cohens_d(q('full'), q('constrained')):.2f}.")
        md.append("Diversity (mean pairwise word-set distance): " + ", ".join(
            f"{c} {diversity(data[c][0]):.2f}" for c in COND[1:]) + ".")
        ex = data["full"][0][0]
        md.append(f"\nExample (full system):\n\n```\n{ex.text()}\n```")

    md.append("""
## How to read this (and its limits)

* The metrics are **automatic proxies**. Typicality and cohesion are calibrated on the real poems
  (leave-one-poem-out), so 'typical enough' is learned from the inspiring set, not set by hand.
* Some components (syntax, typicality, meter, cohesion) are also used by the generator to pick
  lines and poems, so `full` is partly graded on what it optimised. The honest check is the
  independent **human evaluation** (`src/human_eval.py`) and the readability of the examples.
* Typicality here is feature-based (line length, function-word ratio, word length, variety) because
  a word-bigram likelihood ratio could not separate the categories out-of-sample with so few poems.
* Cohesion is a weak proxy (word co-occurrence inside the corpus); coherence between lines is the
  known weakness of Markov generation and the numbers should be read that way.
""")
    with open(os.path.join(a.outdir, "evaluation_summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    fields = sorted({k for r in rows_csv for k in r}, key=lambda k: (k not in ("category", "condition", "text"), k))
    with open(os.path.join(a.outdir, "evaluation_poems.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows_csv)

    # ---- profile plot
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True)
    for ax, cat in zip(axes, CATS):
        data = all_data[cat]
        keys = [k for k in PROFILE if k in data["full"][1][0] and k != "novelty"] + ["novelty"]
        width = 0.2
        for i, c in enumerate(COND):
            s = summarise(data[c][1])
            vals = [s[k][0] if k in s else 0 for k in keys]
            ax.bar([x + i * width for x in range(len(keys))], vals, width, label=c, color=COLORS[c])
        ax.set_xticks([x + 1.5 * width for x in range(len(keys))])
        ax.set_xticklabels(keys, rotation=40, ha="right")
        ax.set_title(cat)
        ax.set_ylim(0, 1.05)
    axes[0].set_ylabel("score (0-1)")
    axes[0].legend(frameon=False)
    plt.tight_layout()
    plt.savefig(os.path.join(a.outdir, "evaluation_profile.png"), dpi=150)
    print("Wrote evaluation_summary.md, evaluation_poems.csv, evaluation_profile.png to", a.outdir)


if __name__ == "__main__":
    main()
