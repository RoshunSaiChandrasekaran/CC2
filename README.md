# Poem Generator (Computational Creativity, LIACS)

A Python poem generator for three forms: **quatrain**, **Shakespearean sonnet** (ABAB CDCD EFEF GG, iambic
pentameter) and **free verse**. Method: **word-level Markov chains + rhyme/meter constraints + generate-and-rank**.

Positioning (from the NLG lecture): Markov chains sit at the *simple* end of the poetry-generation methods
(templates, grammars, Markov chains, ... neural networks). So the engineering is kept deliberately plain and the
weight of the project is on **how good the poems actually are** (see Evaluation).

## Status
| Deliverable | Status |
|---|---|
| Inspiring set (42 poems, 3 categories) | Done: `data/inspiring_set.json` |
| Generator | Done: `src/` |
| Evaluation (automatic + human kit) | Done: `src/evaluate.py`, `src/human_eval.py` |
| GenAI-assisted presentation of 3 poems | Not started |
| ICCC report | Not started |

## Install and run
```bash
pip install -r requirements.txt            # pronouncing (CMU dictionary) + matplotlib
python3 src/main.py --category sonnet --theme night --top 3 --seed 42
python3 src/main.py --category all --top 2 --seed 1
python3 src/evaluate.py --n 40 --pool 10 --seed 7      # ~2 min
python3 src/human_eval.py make --n 4 --seed 1          # blind rating sheet
```
`main.py` options: `--category {quatrain,sonnet,free_verse,all}`, `--theme WORD` (any content word of the corpus),
`--top`, `--pool`, `--stanzas` (quatrain), `--lines` (free verse), `--order2` (lower = more novel), `--seed`.

## Files
| File | What it does |
|---|---|
| `data/inspiring_set.json` | 42 public-domain poems (18 quatrain, 13 sonnet, 11 free verse). Blank line = stanza break. Transcriptions are from memory plus partial web checks: spot-check before quoting exact text. |
| `src/phonetics.py` | Tokeniser, syllables, stress, rhyme test and meter fit (CMU dictionary). |
| `src/lm.py` | Corpus loader; forward and **backward** order-2 Markov chain (target category weighted x4); n-gram LM; word associations (PPMI) used for themes and cohesion. |
| `src/generator.py` | The generator: form planning, rhyme-word picking, backward line building, candidate scoring, poem ranking, plain-Markov baseline. |
| `src/metrics.py` | The evaluator (the centre of the project): form, typicality, syntax, cohesion, fluency, novelty, quality Q and fitness F. |
| `src/main.py` | Command-line generation; writes `outputs/best_poems_<category>.txt`. |
| `src/evaluate.py` | Experiment: real vs baseline vs constrained vs full; writes summary table, CSV, plot. |
| `src/human_eval.py` | Blind rating sheet for the group + analysis script. |

## How it works
1. **Form.** Sonnet: fixed scheme, 10 syllables. Quatrain: scheme sampled from those found in the inspiring set's
   4-line stanzas (learned: ABCB, AABB, ABAB, ...), with ballad (8,6,8,6), tetrameter (8) or trochaic (7) lines.
   Free verse: no rhyme or meter, line lengths sampled from the real free-verse poems.
2. **Theme.** A word is chosen (or given); words associated with it (PPMI over nearby lines) are boosted.
3. **Rhyme by construction.** Rhyme families come from the CMU dictionary over the corpus vocabulary. Each line is built
   **backwards** from its rhyme word with the reverse Markov chain until the syllable count is exact.
4. **Line choice.** A pool of valid lines is scored (meter, syntax, typicality, line starter, theme); copies of
   5+ word runs from the inspiring set are rejected.
5. **Poem ranking.** Several whole poems are generated and ranked by the full evaluator.

## Evaluation
Quality is a *profile*, each component 0-1, not one magic number:
* **form**: rhyme (CMU test), syllable regularity, meter (stress fit; one-syllable words are flexible)
* **typicality** (Ritchie's typ): z-distance of line length, function-word ratio, word length, variety to the real poems
  of the category; 'typical enough' is **learned** (leave-one-poem-out), not an arbitrary threshold
* **syntax**: class-bigram model (function words literal, content words -> C) catches ungrammatical word order
* **cohesion**: similarity of neighbouring lines in a PPMI space (weak proxy; coherence is Markov's known weakness)
* **fluency**: syntax + dangling endings ('...of the'), repeated words, implausible line starts
* **novelty** (Ritchie): new word trigrams and no long copied runs vs the inspiring set
* **Q** = weighted mix of the above; **F** = Q x (0.6 + 0.4 x novelty), used for ranking

`evaluate.py` compares four conditions: *real* poems, a plain Markov *baseline*, *constrained* (no ranking), *full*.
**Limits to report honestly:** several components are also used by the generator to choose lines, so `full` is
partly graded on what it optimised; the independent check is the blind human evaluation (`human_eval.py`).
The Markov chain gives well-formed lines that rhyme and scan but little meaning across lines.
