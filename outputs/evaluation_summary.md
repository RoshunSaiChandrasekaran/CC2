# Evaluation summary

40 poems per condition per category (seed 7); mean (sd). All scores 0-1.

`real` rows are the inspiring-set poems themselves (novelty not applicable).


## quatrain

| condition | rhyme | syllable | meter | typicality | syntax | cohesion | fluency | novelty | quality | fitness |
|---|---|---|---|---|---|---|---|---|---|---|
| real | 0.78 (0.41) | 0.90 (0.10) | 0.94 (0.04) | 0.76 (0.33) | 0.74 (0.20) | 0.30 (0.35) | 0.87 (0.10) | - | 0.68 (0.13) | - |
| salad | 0.00 (0.00) | 0.65 (0.07) | 0.87 (0.03) | 0.00 (0.00) | 1.00 (0.00) | 0.02 (0.03) | 0.93 (0.01) | 1.00 (0.00) | 0.36 (0.01) | 0.36 (0.01) |
| shuffled | 0.05 (0.12) | 0.68 (0.07) | 0.92 (0.03) | 0.35 (0.38) | 0.79 (0.10) | 0.06 (0.05) | 0.89 (0.05) | 0.01 (0.01) | 0.43 (0.07) | 0.26 (0.04) |
| baseline | 0.03 (0.10) | 0.61 (0.08) | 0.92 (0.03) | 0.21 (0.32) | 0.74 (0.13) | 0.05 (0.04) | 0.86 (0.07) | 0.29 (0.07) | 0.39 (0.05) | 0.28 (0.04) |
| constrained | 1.00 (0.00) | 1.00 (0.00) | 0.93 (0.03) | 0.98 (0.08) | 0.72 (0.13) | 0.10 (0.08) | 0.85 (0.07) | 0.57 (0.08) | 0.69 (0.04) | 0.57 (0.03) |
| full | 1.00 (0.00) | 1.00 (0.00) | 0.94 (0.02) | 0.96 (0.09) | 0.94 (0.06) | 0.43 (0.13) | 0.97 (0.03) | 0.57 (0.09) | 0.81 (0.04) | 0.67 (0.04) |

Effect size on quality (Cohen's d): constrained vs baseline = 6.76, full vs constrained = 3.25.

**Metric sanity check:** PASS: both negative controls score clearly below real poems.
Win rates on quality: real > shuffled 95%, full > shuffled 100%, real > full 18%.
Diversity (mean pairwise word-set distance): salad 0.98, shuffled 0.89, baseline 0.87, constrained 0.87, full 0.87.

Example (full system):

```
It the whole long day what dread hand,
In sight of finished years,
The thing to me when the trees bow,
When just in beauty's brow.

And when the slow dark secret love,
Love of the day's journey,
Love of the jabberwock my foe,
Love that bares her speak low.

The slow dark is an ever fixed,
I love abide and meet,
Sir I think my love of the rest
Love of true account lest.
```

## sonnet

| condition | rhyme | syllable | meter | typicality | syntax | cohesion | fluency | novelty | quality | fitness |
|---|---|---|---|---|---|---|---|---|---|---|
| real | 0.46 (0.31) | 0.91 (0.05) | 0.91 (0.03) | 0.74 (0.33) | 0.92 (0.11) | 0.39 (0.31) | 0.96 (0.06) | - | 0.68 (0.10) | - |
| salad | 0.00 (0.02) | 0.29 (0.10) | 0.73 (0.05) | 0.00 (0.00) | 1.00 (0.00) | 0.03 (0.07) | 0.93 (0.01) | 1.00 (0.00) | 0.31 (0.02) | 0.31 (0.02) |
| shuffled | 0.01 (0.04) | 0.48 (0.13) | 0.85 (0.05) | 0.03 (0.09) | 0.96 (0.10) | 0.05 (0.08) | 0.97 (0.05) | 0.01 (0.01) | 0.36 (0.04) | 0.22 (0.02) |
| baseline | 0.01 (0.04) | 0.26 (0.08) | 0.83 (0.04) | 0.00 (0.00) | 0.94 (0.09) | 0.02 (0.04) | 0.96 (0.05) | 0.28 (0.06) | 0.32 (0.02) | 0.23 (0.02) |
| constrained | 1.00 (0.00) | 1.00 (0.00) | 0.81 (0.04) | 0.75 (0.24) | 0.93 (0.10) | 0.20 (0.27) | 0.95 (0.05) | 0.52 (0.04) | 0.69 (0.09) | 0.56 (0.08) |
| full | 1.00 (0.00) | 1.00 (0.00) | 0.88 (0.04) | 0.89 (0.12) | 1.00 (0.00) | 0.99 (0.04) | 0.99 (0.01) | 0.56 (0.05) | 0.96 (0.02) | 0.79 (0.03) |

Effect size on quality (Cohen's d): constrained vs baseline = 5.35, full vs constrained = 4.06.

**Metric sanity check:** PASS: both negative controls score clearly below real poems.
Win rates on quality: real > shuffled 100%, full > shuffled 100%, real > full 0%.
Diversity (mean pairwise word-set distance): salad 0.96, shuffled 0.87, baseline 0.86, constrained 0.84, full 0.83.

Example (full system):

```
The road wind up all losses are restored
And candle light is spread with that which goes,
That man's work or birds or his vorpal sword
Else swoon to time that catch somewhere O rose.

To add divide and on the horses heads,
In the breath that it alteration finds
Gives life to the winds that will need be beds,
The silence of the questions of true minds.

In the silence of soul who come to hide,
Come with my wrath did sun more rich in hope,
And to the speaking silence of one wide
From art the day at night with that man's scope?

As thou art more rich in his glory fight
A love more rich in death's dateless night.
```

## free_verse

| condition | typicality | syntax | cohesion | fluency | novelty | quality | fitness |
|---|---|---|---|---|---|---|---|
| real | 0.80 (0.24) | 0.54 (0.24) | 0.37 (0.37) | 0.76 (0.13) | - | 0.62 (0.14) | - |
| salad | 0.00 (0.00) | 0.99 (0.02) | 0.09 (0.09) | 0.92 (0.02) | 1.00 (0.00) | 0.36 (0.04) | 0.36 (0.04) |
| shuffled | 1.00 (0.00) | 0.33 (0.13) | 0.11 (0.09) | 0.66 (0.07) | 0.01 (0.02) | 0.52 (0.04) | 0.32 (0.03) |
| baseline | 1.00 (0.00) | 0.41 (0.13) | 0.13 (0.13) | 0.69 (0.07) | 0.28 (0.07) | 0.54 (0.06) | 0.39 (0.04) |
| constrained | 0.98 (0.07) | 0.47 (0.13) | 0.21 (0.15) | 0.73 (0.07) | 0.49 (0.08) | 0.59 (0.08) | 0.47 (0.06) |
| full | 1.00 (0.00) | 0.83 (0.13) | 0.97 (0.11) | 0.91 (0.07) | 0.51 (0.07) | 0.96 (0.05) | 0.77 (0.05) |

Effect size on quality (Cohen's d): constrained vs baseline = 0.64, full vs constrained = 5.76.

**Metric sanity check:** WARNING: shuffled score within 0.15 of real poems, so 'quality' cannot tell them apart.
Win rates on quality: real > shuffled 70%, full > shuffled 100%, real > full 1%.
Diversity (mean pairwise word-set distance): salad 0.96, shuffled 0.88, baseline 0.87, constrained 0.87, full 0.85.

Example (full system):

```
Or eye unused to the nation's freight handler,
I hear america singing his as long time the rest,
The darkness and diagrams to time,
When the lesson done.

Of labour light denied,
Or birds or the powerful play,
Or birds sang
Gave doth now like sleeping flowers.

What art the day
The day at night air and in its soft deceitful wiles,
Night sleep death and so quiet and bright
That mighty heart began to night my childhood's faith.

And dark hours begin.
```

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
