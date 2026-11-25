import argparse
import csv
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(__file__))
from planner import make_plan
import matplotlib                                               
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                 

from generator import GenConfig, PoemGenerator                  
from lm import Associations, Corpus, Poem                       
from metrics import Evaluator, cohens_d, diversity, summarise   

CATS = ["quatrain", "sonnet", "free_verse"]
PROFILE = ["rhyme", "syllable", "meter", "typicality", "syntax", "cohesion", "fluency", "novelty", "quality"]
TABLE = PROFILE + ["fitness"]
COND = ["real", "salad", "shuffled", "baseline", "constrained", "full"]
COLORS = {"real": "#7a7a7a", "salad": "#8e5bb5", "shuffled": "#b5483a",
          "baseline": "#c9a227", "constrained": "#3b7dd8", "full": "#1f9d6b"}


def first_valid(g, plan, tries=50):
    for _ in range(tries):
        p = g.generate_poem(plan)
        if p is not None:
            return p
    raise RuntimeError("plan could not be realised")


def shuffled_poem(corpus, cat, plan, rng):
    """NEGATIVE CONTROL: grammatical real lines in random order. Should lose on cohesion/rhyme."""
    pool = [l for p in corpus.poems for l in p.lines]
    return Poem(cat, [[rng.choice(pool) for _ in range(sz)] for sz in plan.block_sizes()],
                meta={"control": "shuffled"})


def salad_poem(corpus, cat, plan, rng):
    """NEGATIVE CONTROL: random vocabulary words, realistic line lengths. Should score lowest."""
    vocab = sorted(corpus.vocab)
    lengths = [len(t) for p in corpus.of_category(cat) for t in p.token_lines]
    return Poem(cat, [[" ".join(rng.choice(vocab) for _ in range(rng.choice(lengths)))
                       for _ in range(sz)] for sz in plan.block_sizes()],
                meta={"control": "salad"})


def win_rate(a, b):
    """P(a random item from a scores higher than a random item from b)."""
    return sum(x > y for x in a for y in b) / (len(a) * len(b))


def run_category(corpus, assoc, cat, n, pool, seed):
    ev = Evaluator(corpus, cat, assoc)
    rng = random.Random(seed)
    plans = [make_plan(rng, assoc, "short", cat) for _ in range(n)]
    data = {"real": (ev.ref_units, [ev.evaluate(u, with_novelty=False) for u in ev.ref_units])}
    rng_c = random.Random(seed + 3)
    for name, make in (("salad", salad_poem), ("shuffled", shuffled_poem)):
        ps = [make(corpus, cat, pl, rng_c) for pl in plans]
        data[name] = (ps, [ev.evaluate(p) for p in ps])

    g = PoemGenerator(corpus, cat, GenConfig(), seed=seed, evaluator=ev)
    base = [g.baseline_poem(pl) for pl in plans]
    data["baseline"] = (base, [ev.evaluate(p) for p in base])

    g = PoemGenerator(corpus, cat, GenConfig(line_pool=1), seed=seed + 1, evaluator=ev)
    cons = [first_valid(g, pl) for pl in plans]
    data["constrained"] = (cons, [ev.evaluate(p) for p in cons])

    g = PoemGenerator(corpus, cat, GenConfig(), seed=seed + 2, evaluator=ev)
    full, fm = [], []
    for pl in plans:
        (p, m), = g.generate(top_k=1, plan=pl, pool=pool)
        full.append(p)
        fm.append(m)
    data["full"] = (full, fm)
    return data


def main():
    here = os.path.dirname(__file__)
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(here, "..", "inspiring_set.json"))
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
        q = lambda c: [m["quality"] for m in data[c][1]]      
        md.append(f"\nEffect size on quality (Cohen's d): constrained vs baseline = "
                  f"{cohens_d(q('constrained'), q('baseline')):.2f}, "
                  f"full vs constrained = {cohens_d(q('full'), q('constrained')):.2f}.")
        qm = {c: statistics.mean(q(c)) for c in COND}
        bad = [c for c in ("salad", "shuffled") if qm[c] > qm["real"] - 0.15]
        md.append("\n**Metric sanity check:** " + (
            "PASS: both negative controls score clearly below real poems." if not bad else
            f"WARNING: {', '.join(bad)} score within 0.15 of real poems, so 'quality' cannot "
            "tell them apart."))
        md.append(f"Win rates on quality: real > shuffled {win_rate(q('real'), q('shuffled')):.0%}, "
                  f"full > shuffled {win_rate(q('full'), q('shuffled')):.0%}, "
                  f"real > full {win_rate(q('real'), q('full')):.0%}.")
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
        width = 0.13
        for i, c in enumerate(COND):
            s = summarise(data[c][1])
            vals = [s[k][0] if k in s else 0 for k in keys]
            ax.bar([x + i * width for x in range(len(keys))], vals, width, label=c, color=COLORS[c])
        ax.set_xticks([x + 2.5 * width for x in range(len(keys))])
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
