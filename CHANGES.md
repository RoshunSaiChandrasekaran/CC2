# Changes on top of CC2-improvements

1. **Titles.** New `src/titler.py`; `main.py` now prints a title for every poem and stores it in
   `outputs/best_poems_*.txt` (see README, step 7).
2. **Different ideas in the best poems.** `PoemGenerator.generate_varied()` (new) gives every top poem its own
   plan; `make_plan(..., avoid=...)` picks a premise that has not been used yet. `generate()` is unchanged, so
   `evaluate.py` and `human_eval.py` behave exactly as before (checked: identical evaluation tables).
3. **Bug fix.** `evaluate.py` and `human_eval.py` still looked for `data/inspiring_set.json` and crashed by default
   after the file moved to the project root. Both now use `inspiring_set.json`.
4. **Refreshed outputs.** The shipped `evaluation_summary.md`, `evaluation_poems.csv` and `evaluation_profile.png`
   were older than the code (re-running the unchanged code gave different numbers). They were regenerated
   (`evaluate.py --n 40 --pool 10 --seed 7`); `best_poems_*.txt` were regenerated with `--seed 7`.
5. **README.** Updated: planner and titler files, `--length`, no more `--theme`, inspiring set now source-checked
   (`SOURCES.md`).
