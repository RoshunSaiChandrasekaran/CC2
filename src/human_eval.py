"""Blind human-evaluation kit (independent of the automatic metrics).

1) Make a sheet: real poems, baseline poems and full-system poems, shuffled and
   anonymised. Every group member rates their own copy.

       python3 src/human_eval.py make --n 4 --seed 1

   -> outputs/human_eval_sheet.csv   (give each rater a copy: sheet_roshun.csv, ...)
   -> outputs/human_eval_key.csv     (id -> source; DO NOT show raters)

2) Fill the five rating columns (1-5; last column yes/no), then analyse:

       python3 src/human_eval.py analyze --ratings outputs/sheet_roshun.csv outputs/sheet_nithin.csv outputs/sheet_melisa.csv
"""
import argparse
import csv
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(__file__))
from generator import GenConfig, PoemGenerator            # noqa: E402
from lm import Associations, Corpus                       # noqa: E402
from metrics import Evaluator                             # noqa: E402

CATS = ["quatrain", "sonnet", "free_verse"]
DIMS = ["fluency", "coherence", "sound_and_form", "overall"]
GUESS = "human_written"
HEAD = ["id", "category", "poem"] + DIMS + [GUESS]


def make(a):
    corpus = Corpus(a.data)
    assoc = Associations(corpus)
    rng = random.Random(a.seed)
    items = []
    for cat in CATS:
        ev = Evaluator(corpus, cat, assoc)
        g = PoemGenerator(corpus, cat, seed=a.seed, evaluator=ev)
        for u in rng.sample(ev.ref_units, min(a.n, len(ev.ref_units))):
            items.append((cat, "real", u))
        for _ in range(a.n):
            items.append((cat, "baseline", g.baseline_poem()))
        for _ in range(a.n):
            (p, _m), = g.generate(top_k=1)
            items.append((cat, "full", p))
    rng.shuffle(items)
    os.makedirs(a.outdir, exist_ok=True)
    with open(os.path.join(a.outdir, "human_eval_sheet.csv"), "w", newline="", encoding="utf-8") as fs, \
         open(os.path.join(a.outdir, "human_eval_key.csv"), "w", newline="", encoding="utf-8") as fk:
        ws, wk = csv.writer(fs), csv.writer(fk)
        ws.writerow(HEAD)
        wk.writerow(["id", "category", "source"])
        for i, (cat, src, p) in enumerate(items, 1):
            ws.writerow([i, cat, p.text().replace("\n\n", " // ").replace("\n", " / ")] + [""] * (len(DIMS) + 1))
            wk.writerow([i, cat, src])
    print(f"Wrote {len(items)} poems to {a.outdir}/human_eval_sheet.csv (+ key). Rate: " +
          ", ".join(DIMS) + " from 1 (bad) to 5 (good); human_written = yes/no.")


def analyze(a):
    key = {}
    with open(a.key, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key[r["id"]] = (r["category"], r["source"])
    ratings = []                                   # (rater, id, dim -> value, guess)
    for path in a.ratings:
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if not r["overall"].strip():
                    continue
                ratings.append((os.path.basename(path), r["id"], {d: float(r[d]) for d in DIMS},
                                r[GUESS].strip().lower().startswith("y")))
    out = [f"# Human evaluation ({len(a.ratings)} raters, {len(ratings)} ratings)\n",
           "| source | " + " | ".join(DIMS) + " | rated 'human-written' |", "|---|" + "---|" * (len(DIMS) + 1)]
    for src in ("real", "baseline", "full"):
        rs = [r for r in ratings if key[r[1]][1] == src]
        if not rs:
            continue
        cells = [f"{statistics.mean(r[2][d] for r in rs):.2f}" for d in DIMS]
        out.append(f"| {src} | " + " | ".join(cells) + f" | {100 * sum(r[3] for r in rs) / len(rs):.0f}% |")
    out.append("\nPer category (overall score):\n")
    for cat in CATS:
        parts = []
        for src in ("real", "baseline", "full"):
            rs = [r for r in ratings if key[r[1]] == (cat, src)]
            if rs:
                parts.append(f"{src} {statistics.mean(r[2]['overall'] for r in rs):.2f}")
        out.append(f"* {cat}: " + ", ".join(parts))
    raters = sorted({r[0] for r in ratings})
    if len(raters) > 1:                            # agreement: mean pairwise Pearson on 'overall'
        by = {x: {r[1]: r[2]["overall"] for r in ratings if r[0] == x} for x in raters}
        cors = []
        for i in range(len(raters)):
            for j in range(i + 1, len(raters)):
                ids = sorted(set(by[raters[i]]) & set(by[raters[j]]))
                if len(ids) > 2:
                    xs, ys = [by[raters[i]][k] for k in ids], [by[raters[j]][k] for k in ids]
                    if statistics.pstdev(xs) and statistics.pstdev(ys):
                        mx, my = statistics.mean(xs), statistics.mean(ys)
                        cors.append(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) /
                                    (len(xs) * statistics.pstdev(xs) * statistics.pstdev(ys)))
        if cors:
            out.append(f"\nInter-rater agreement (mean pairwise Pearson r on 'overall'): {statistics.mean(cors):.2f}")
    text = "\n".join(out)
    print(text)
    with open(os.path.join(os.path.dirname(a.key), "human_eval_results.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


def main():
    here = os.path.dirname(__file__)
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make")
    m.add_argument("--data", default=os.path.join(here, "..", "data", "inspiring_set.json"))
    m.add_argument("--n", type=int, default=4, help="poems per source per category")
    m.add_argument("--seed", type=int, default=1)
    m.add_argument("--outdir", default=os.path.join(here, "..", "outputs"))
    an = sub.add_parser("analyze")
    an.add_argument("--key", default=os.path.join(here, "..", "outputs", "human_eval_key.csv"))
    an.add_argument("--ratings", nargs="+", required=True)
    a = ap.parse_args()
    make(a) if a.cmd == "make" else analyze(a)


if __name__ == "__main__":
    main()
