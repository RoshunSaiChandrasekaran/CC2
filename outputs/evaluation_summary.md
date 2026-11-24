# Evaluation summary

40 poems per condition per category (seed 7); mean (sd). All scores 0-1.

`real` rows are the inspiring-set poems themselves (novelty not applicable).


## quatrain

| condition | rhyme | syllable | meter | typicality | syntax | cohesion | fluency | novelty | quality | fitness |
|---|---|---|---|---|---|---|---|---|---|---|
| real | 0.78 (0.41) | 0.90 (0.10) | 0.98 (0.03) | 0.92 (0.13) | 0.74 (0.20) | 0.30 (0.35) | 0.87 (0.10) | - | 0.71 (0.13) | - |
| baseline | 0.03 (0.10) | 0.61 (0.08) | 0.97 (0.02) | 0.61 (0.23) | 0.74 (0.13) | 0.05 (0.04) | 0.86 (0.07) | 0.29 (0.07) | 0.45 (0.04) | 0.33 (0.03) |
| constrained | 1.00 (0.00) | 1.00 (0.00) | 0.98 (0.02) | 1.00 (0.03) | 0.72 (0.13) | 0.10 (0.08) | 0.85 (0.07) | 0.57 (0.08) | 0.70 (0.03) | 0.58 (0.03) |
| full | 1.00 (0.00) | 1.00 (0.00) | 0.99 (0.02) | 0.99 (0.02) | 0.95 (0.05) | 0.45 (0.12) | 0.97 (0.03) | 0.58 (0.06) | 0.83 (0.04) | 0.69 (0.04) |

Effect size on quality (Cohen's d): constrained vs baseline = 6.26, full vs constrained = 3.68.
Diversity (mean pairwise word-set distance): baseline 0.87, constrained 0.87, full 0.86.

Example (full system):

```
And to the vorpal sword in hand,
Forests of finished years,
The hand or stand under trees bow,
When just in beauty's brow.

And to the slow dark secret love,
Love of the day's journey,
Love of the jabberwock my foe,
Love that bares her speak low.

The slow dark is an ever fixed,
I love abide and meet,
Hope love of snow upon the rest
Love of true account lest.
```

## sonnet

| condition | rhyme | syllable | meter | typicality | syntax | cohesion | fluency | novelty | quality | fitness |
|---|---|---|---|---|---|---|---|---|---|---|
| real | 0.46 (0.31) | 0.91 (0.05) | 0.95 (0.03) | 0.96 (0.10) | 0.92 (0.11) | 0.39 (0.31) | 0.96 (0.06) | - | 0.71 (0.10) | - |
| baseline | 0.01 (0.04) | 0.26 (0.08) | 0.89 (0.04) | 0.02 (0.06) | 0.94 (0.09) | 0.02 (0.04) | 0.96 (0.05) | 0.28 (0.06) | 0.33 (0.02) | 0.24 (0.02) |
| constrained | 1.00 (0.00) | 1.00 (0.00) | 0.87 (0.04) | 0.98 (0.04) | 0.93 (0.10) | 0.20 (0.27) | 0.95 (0.05) | 0.52 (0.04) | 0.73 (0.09) | 0.59 (0.07) |
| full | 1.00 (0.00) | 1.00 (0.00) | 0.94 (0.03) | 0.98 (0.04) | 1.00 (0.02) | 0.99 (0.02) | 0.99 (0.01) | 0.59 (0.05) | 0.99 (0.01) | 0.82 (0.02) |

Effect size on quality (Cohen's d): constrained vs baseline = 6.23, full vs constrained = 4.16.
Diversity (mean pairwise word-set distance): baseline 0.86, constrained 0.84, full 0.83.

Example (full system):

```
In death's second self that which goes before;
Wrath did he kindly stopped for precious friends,
In the night doth like to go to show more,
Like stout cortez when yellow leaves or bends!

And is a far more red than in the west,
And useless though my verse shall death to hide,
Better after death brag thou know who best,
And is death to the main of light denied.

Come to my very houses seem asleep,
Come in the air so live ever or eyes,
Come with the rest me in the roof so deep,
And delves the speaking silence of the skies!

And I see around the powerful play,
And cheeks and often is death bed by day!
```

## free_verse

| condition | typicality | syntax | cohesion | fluency | novelty | quality | fitness |
|---|---|---|---|---|---|---|---|
| real | 0.90 (0.08) | 0.54 (0.24) | 0.37 (0.37) | 0.76 (0.13) | - | 0.64 (0.14) | - |
| baseline | 1.00 (0.01) | 0.41 (0.13) | 0.13 (0.13) | 0.69 (0.07) | 0.28 (0.07) | 0.54 (0.06) | 0.39 (0.04) |
| constrained | 0.98 (0.04) | 0.47 (0.13) | 0.21 (0.15) | 0.73 (0.07) | 0.49 (0.08) | 0.59 (0.07) | 0.47 (0.06) |
| full | 1.00 (0.02) | 0.83 (0.10) | 0.96 (0.08) | 0.92 (0.05) | 0.51 (0.07) | 0.95 (0.03) | 0.77 (0.04) |

Effect size on quality (Cohen's d): constrained vs baseline = 0.67, full vs constrained = 6.53.
Diversity (mean pairwise word-set distance): baseline 0.87, constrained 0.87, full 0.85.

Example (full system):

```
I hear the grown up in the lecture room,
Ever a child;
Come with soft deceitful wiles
And more temperate.

And time the manxome foe;
To time thou dost smile,
And you O my love thee to time the same
Every square yard of a dream.

Night sleep death to hide;
Or look at night the other way,
Of the night,
The whole long day at night?

Or sleep death and candle light?
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
