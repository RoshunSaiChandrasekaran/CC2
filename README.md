# Poem Generator

A Python poem generator for three forms: **quatrain**, **Shakespearean sonnet** (ABAB CDCD EFEF GG, iambic
pentameter) and **free verse**. Method: **word-level Markov chains + rhyme/meter constraints + generate-and-rank**.

Positioning (from the NLG lecture): Markov chains sit at the _simple_ end of the poetry-generation methods
(templates, grammars, Markov chains, ... neural networks). So the engineering is kept deliberately plain and the
weight of the project is on **how good the poems actually are** (see Evaluation).

## Status

| Deliverable                            | Status                                       |
| -------------------------------------- | -------------------------------------------- |
| Inspiring set (42 poems, 3 categories) | Done: `inspiring_set.json`                   |
| Generator                              | Done: `src/`                                 |
| Evaluation (automatic + human kit)     | Done: `src/evaluate.py`, `src/human_eval.py` |
| GenAI-assisted presentation of 3 poems | Not started                                  |
| ICCC report                            | Not started                                  |

## Install and run

```bash
pip install -r requirements.txt            # pronouncing (CMU dictionary) + matplotlib
python3 src/main.py --category sonnet --top 3 --seed 42
python3 src/main.py --category all --top 2 --seed 1
python3 src/evaluate.py --n 40 --pool 10 --seed 7      # ~2 min
python3 src/human_eval.py make --n 4 --seed 1          # blind rating sheet
```

`main.py` options: `--category {quatrain,sonnet,free_verse,all}`, `--length {short,medium,long}` (a sonnet is always 14 lines),
`--top`, `--pool`, `--order2` (lower = more novel), `--seed`. Each of the `--top` poems gets its own plan (a different
idea where possible) and a title.

## Files

| File                 | What it does                                                                                                                                                                             |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `inspiring_set.json` | 42 public-domain poems (18 quatrain, 13 sonnet, 11 free verse). Blank line = stanza break. Every poem was compared word by word with a published text; each carries a `source` field. |
| `SOURCES.md`         | Table of all 42 poems with the pages used, the edition and known textual variants (cite this in the report). |
| `src/planner.py`     | Plans a poem before it is written: a premise (idea), moods, imagery, a role per stanza (introduction ... reversal, ending) and the stop checks a finished poem must pass. |
| `src/titler.py`      | Gives each generated poem a short title built from words of the poem itself (see below). |
| `src/phonetics.py`   | Tokeniser, syllables, stress, rhyme test and meter fit (CMU dictionary).                                                                                                                 |
| `src/lm.py`          | Corpus loader; forward and **backward** order-2 Markov chain (target category weighted x4); n-gram LM; word associations (PPMI) used for themes and cohesion.                            |
| `src/generator.py`   | The generator: form planning, rhyme-word picking, backward line building, candidate scoring, poem ranking, plain-Markov baseline.                                                        |
| `src/metrics.py`     | The evaluator (the centre of the project): form, typicality, syntax, cohesion, fluency, novelty, quality Q and fitness F.                                                                |
| `src/main.py`        | Command-line generation; writes `outputs/best_poems_<category>.txt`.                                                                                                                     |
| `src/evaluate.py`    | Experiment: real vs baseline vs constrained vs full; writes summary table, CSV, plot.                                                                                                    |
| `src/human_eval.py`  | Blind rating sheet for the group + analysis script.                                                                                                                                      |

## How it works

1. **Form.** Sonnet: fixed scheme, 10 syllables. Quatrain: scheme sampled from those found in the inspiring set's
   4-line stanzas (learned: ABCB, AABB, ABAB, ...), with ballad (8,6,8,6), tetrameter (8) or trochaic (7) lines.
   Free verse: no rhyme or meter, line lengths sampled from the real free-verse poems.
2. **Plan.** `planner.py` picks a premise (an idea with theme and counter-theme words), moods and an imagery style, and
   gives each stanza a role (introduction, development, complication, reversal, ending). Words associated with the
   role's theme words (PPMI over nearby lines) are boosted in that stanza; imagery words are boosted throughout.
3. **Rhyme by construction.** Rhyme families come from the CMU dictionary over the corpus vocabulary. Each line is built
   **backwards** from its rhyme word with the reverse Markov chain until the syllable count is exact.
4. **Line choice.** A pool of valid lines is scored (meter, syntax, typicality, line starter, theme); copies of
   5+ word runs from the inspiring set are rejected.
5. **Poem ranking.** Several whole poems are generated and ranked by the full evaluator.
6. **Different ideas in the best poems.** `generate()` ranks a pool built from one plan, so its top poems share one
   idea. `main.py` therefore uses `generate_varied()`: every output slot gets its own plan (different premise where
   possible), a pool is built for it and only that pool's best poem is kept. The evaluation is unaffected, because
   `evaluate.py` already draws a fresh plan for every poem. Note that the idea is a *plan*: the Markov chain is only
   steered towards its words, so a poem does not really express the idea.
7. **Titles.** The inspiring set's titles are short noun phrases ("Fog", "The Tyger", "Bright Star"). A title is a
   1-4 word phrase taken from the poem itself (or its most important nouns, e.g. "Night and Silence"), scored on
   salience (repeated or planned words), distinctiveness (rare across the inspiring set), grammar (class-bigram score)
   and noun ending (learned from the corpus). It never repeats a real title, never starts with "Of", and is never
   repeated within one output file. Titles are presentation only: they are not part of the evaluation, and the blind
   human-rating sheet leaves them out.

## Evaluation

Quality is a _profile_, each component 0-1, not one magic number:

- **form**: rhyme (CMU test), syllable regularity, meter (stress fit; one-syllable words are flexible)
- **typicality** (Ritchie's typ): z-distance of line length, function-word ratio, word length, variety to the real poems
  of the category; 'typical enough' is **learned** (leave-one-poem-out), not an arbitrary threshold
- **syntax**: class-bigram model (function words literal, content words -> C) catches ungrammatical word order
- **cohesion**: similarity of neighbouring lines in a PPMI space (weak proxy; coherence is Markov's known weakness)
- **fluency**: syntax + dangling endings ('...of the'), repeated words, implausible line starts
- **novelty** (Ritchie): new word trigrams and no long copied runs vs the inspiring set
- **Q** = weighted mix of the above; **F** = Q x (0.6 + 0.4 x novelty), used for ranking

`evaluate.py` compares four conditions: _real_ poems, a plain Markov _baseline_, _constrained_ (no ranking), _full_.
**Limits to report honestly:** several components are also used by the generator to choose lines, so `full` is
partly graded on what it optimised; the independent check is the blind human evaluation (`human_eval.py`).
The Markov chain gives well-formed lines that rhyme and scan but little meaning across lines.
