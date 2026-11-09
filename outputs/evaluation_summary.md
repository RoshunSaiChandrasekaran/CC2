# Evaluation summary

40 poems per condition per category (seed 7); mean (sd). All scores 0-1.

`real` rows are the inspiring-set poems themselves (novelty not applicable).


## quatrain

| condition | rhyme | syllable | meter | typicality | syntax | cohesion | fluency | novelty | quality | fitness |
|---|---|---|---|---|---|---|---|---|---|---|
| real | 0.79 (0.41) | 0.89 (0.10) | 0.98 (0.03) | 0.92 (0.14) | 0.76 (0.19) | 0.29 (0.34) | 0.87 (0.10) | - | 0.77 (0.09) | - |
| baseline | 0.12 (0.33) | 0.59 (0.12) | 0.97 (0.03) | 0.46 (0.32) | 0.69 (0.17) | 0.06 (0.10) | 0.83 (0.09) | 0.33 (0.14) | 0.48 (0.10) | 0.35 (0.08) |
| constrained | 1.00 (0.00) | 1.00 (0.00) | 0.98 (0.04) | 0.97 (0.07) | 0.76 (0.16) | 0.05 (0.06) | 0.86 (0.08) | 0.53 (0.14) | 0.77 (0.03) | 0.63 (0.05) |
| full | 1.00 (0.00) | 1.00 (0.00) | 0.99 (0.02) | 0.99 (0.03) | 0.95 (0.08) | 0.19 (0.16) | 0.97 (0.04) | 0.72 (0.08) | 0.83 (0.04) | 0.74 (0.04) |

Effect size on quality (Cohen's d): constrained vs baseline = 3.87, full vs constrained = 1.86.
Diversity (mean pairwise word-set distance): baseline 0.93, constrained 0.92, full 0.89.

Example (full system):

```
And I told my tears of space,
In the road wind is high place
Up jack and what shall I find,
The grown up at the road wind.
```

## sonnet

| condition | rhyme | syllable | meter | typicality | syntax | cohesion | fluency | novelty | quality | fitness |
|---|---|---|---|---|---|---|---|---|---|---|
| real | 0.46 (0.31) | 0.91 (0.05) | 0.95 (0.03) | 0.96 (0.10) | 0.92 (0.11) | 0.40 (0.31) | 0.96 (0.06) | - | 0.77 (0.07) | - |
| baseline | 0.01 (0.03) | 0.25 (0.09) | 0.90 (0.04) | 0.02 (0.07) | 0.95 (0.09) | 0.08 (0.12) | 0.96 (0.05) | 0.27 (0.06) | 0.34 (0.04) | 0.24 (0.03) |
| constrained | 1.00 (0.00) | 1.00 (0.00) | 0.87 (0.04) | 0.96 (0.08) | 0.89 (0.12) | 0.18 (0.23) | 0.93 (0.06) | 0.52 (0.04) | 0.80 (0.05) | 0.64 (0.05) |
| full | 1.00 (0.00) | 1.00 (0.00) | 0.95 (0.03) | 0.97 (0.05) | 1.00 (0.00) | 0.74 (0.20) | 1.00 (0.00) | 0.53 (0.06) | 0.93 (0.04) | 0.76 (0.04) |

Effect size on quality (Cohen's d): constrained vs baseline = 9.74, full vs constrained = 2.86.
Diversity (mean pairwise word-set distance): baseline 0.86, constrained 0.84, full 0.84.

Example (full system):

```
In the silence at the winds that man's scope;
Of that seals up jack got and kingdoms seen
And nothing like the sun more rich in hope
The little we have sight of pure serene.

In me count the night morning with my face,
And bright star would I sigh the world is heard,
The moving waters at each changing place
In the main of us late the little bird.

In this dark and the little lamb god bless
He calls himself a little lamb god choose
The world is kingly thousands at recess,
I have seen roses see I seemed to lose.

Or of the vorpal sword in hand dare seize,
Or of the sundown or watch honey bees.
```

## free_verse

| condition | typicality | syntax | cohesion | fluency | novelty | quality | fitness |
|---|---|---|---|---|---|---|---|
| real | 0.90 (0.08) | 0.54 (0.24) | 0.36 (0.36) | 0.76 (0.13) | - | 0.71 (0.09) | - |
| baseline | 0.99 (0.02) | 0.43 (0.16) | 0.12 (0.12) | 0.70 (0.09) | 0.26 (0.07) | 0.67 (0.05) | 0.47 (0.04) |
| constrained | 0.98 (0.04) | 0.41 (0.18) | 0.13 (0.14) | 0.70 (0.09) | 0.48 (0.10) | 0.67 (0.06) | 0.53 (0.06) |
| full | 1.00 (0.01) | 0.94 (0.06) | 0.64 (0.27) | 0.97 (0.03) | 0.49 (0.08) | 0.90 (0.07) | 0.71 (0.05) |

Effect size on quality (Cohen's d): constrained vs baseline = -0.06, full vs constrained = 3.57.
Diversity (mean pairwise word-set distance): baseline 0.89, constrained 0.90, full 0.89.

Example (full system):

```
A man said comrade brother,
Watch the slow dark and height
Ne'er saw a man ever renew'd,
Coral is far more beautifully steep,
And saw a man,
And temples lie,
Tool maker and present,
The sea is a vestige of the air.
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
