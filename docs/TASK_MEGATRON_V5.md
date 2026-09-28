# TASK: PaukMegatron v5 — log scoring: `expertise_score` from log10 of followers and stars

Spec per `TASK_TEMPLATE.md` (mrph). Record: `contour.yaml` (Score Expertise
behavior and examples; Harvest and Store Experts examples), updated by hand in
the same commit as this spec. Previous specs and their actuals:
`docs/TASK_MEGATRON.md`, `_V2.md`, `_V3.md`, `_V4.md` — they keep the old
numbers as history and are not edited.
Executor: Morph, processor `glm` (z-ai/glm-5.3-flash, route sync).

First deck of this project that **patches living files** instead of adding new
ones: 8 existing files, 0 new modules. Touch points were named by the scout
(`mrph scout --seed-from-primer`, run `20260928-132615-a3b30a24`, $0.0234),
not by the orchestrator's grep.

## 1. Why this

`expertise_score = followers + 2 * total_stars` is linear in stars, and stars
are counted over every non-fork repo, so a popular organisation's repo farm
outweighs any person. Measured on `experts.db` after the v4 big smoke
(`smoke-v4-big.log`, 2026-09-28): **63** rows, all 63 carry the linear score;
in **47 of 63** stars are more than half of it (sindresorhus, openai,
huggingface: 94–96 %).

Rank inversions, linear → log (rank among the 63; log formula of §2.3):

| pair (followers / total_stars) | linear | log |
|---|---|---|
| **facebookresearch** 37 728 / 676 993 vs **torvalds** 325 482 / 262 436 | #8 (1 391 714) above #15 (850 354) | #11 (1624) below #10 (1635) |
| **huggingface** 68 981 / 735 420 vs **karpathy** 223 470 / 493 946 | #4 (1 539 821) above #9 (1 211 362) | #8 (1657) below #3 (1674) |
| **facebook** 36 844 / 586 421 vs **microsoft** 130 632 / 428 316 | #10 (1 209 686) above #12 (987 264) | #13 (1610) below #9 (1638) |

28 ordered pairs invert this way (the one with fewer followers wins under
linear, loses under log). The most-followed account in the db, torvalds, is
**#15** under linear and **#10** under log.

The cost of the change is also visible and accepted: zero-star accounts fall
(`claude` 179 905 / 0: #38 → #62, `Microsoft-corp` 45 604 / 0: #57 → #63).

The number this deck is judged by: the torvalds fixtures score **1635** (was
850302) through every path that scores — unit, judge, harvest pipeline,
storage — and a module whose `score_expertise` returns the linear value makes
five test files red.

## 2. Contract

### 2.1. INPUT shapes with addresses

| shape | defined at |
|---|---|
| Expert Profile (`followers` int) | `megatron/parsers.py`, fixture `tests/fixtures/user_torvalds.json` (followers 325466) |
| Repo Stats (`total_stars` int, `languages` dict) | `megatron/parsers.py`; fixture `tests/fixtures/repos_torvalds.json` (non-fork stars 262418); v2 pages `repos_torvalds_page{1,2,3}.json` (262425; page 1 alone 7836) |
| Expert Record | `megatron/processors.py:6` `score_expertise(profile, stats)` — unchanged keys |

### 2.2. OUTPUT shapes

Expert Record keys unchanged. `expertise_score` stays a Python `int` (the
result of `round()` on a float), column `expertise_score INTEGER` unchanged.

### 2.3. Names and the formula

```
expertise_score = round(100*log10(followers+1) + 200*log10(total_stars+1))
```

`math.log10`, built-in `round`. `primary_language` unchanged. Control values,
recomputed from the fixtures (not copied):

| input | old | new |
|---|---|---|
| torvalds: followers 325466, total_stars 262418 (`repos_torvalds.json`) | 850302 | **1635** (1635.0498) |
| minnow: followers 7, total_stars 0 | 7 | **90** (90.309) |
| torvalds via the 3 v2 pages: 325466, 262425 | 850316 | **1635** (1635.0521) |
| torvalds via v2 page 1 only: 325466, 7836 | 341138 | **1330** (1330.08) |
| smoke row B (v3 upsert): 325474, 262428 | 850330 | **1635** (1635.0541) |

Hand-set scores stay as they are: minnow `100` in the store tests,
`user_NN` `i * 10` in `test_storage.py` — all below 1635, orders unchanged.

### 2.4. What must not break

All 80 tests green, **still 80**: no test added, dropped or renamed. In every
edited file only the lines of §2.5 change; every other line byte for byte,
docstrings and comments included (the `"""` count of each file is fixed below).
No other file under `megatron/` or `tests/`, no fixture.

### 2.5. Touch points (scout, verified by line)

| file | lines | owner card (primer) | old → new |
|---|---|---|---|
| `megatron/processors.py` | 10, 20 (+ `import math`) | score (v1) | formula in docstring and code |
| `tests/test_processors.py` | 32, 34, 35, 40, 51, 52, 63 | score (v1) | 850302 → 1635, 7 → 90, msgs |
| `tests/test_score_examples.py` | 71, 81, 82, 102, 111, 119, 120 | score-judge (v1) | 850302 → 1635, 7 → 90, msgs |
| `tests/test_cli.py` | 85 | cli (v2) | `[850302, 7]` → `[1635, 90]` |
| `tests/test_harvest_e2e.py` | 102, 138, 139, 161, 162 | e2e (v2) | 850316 → 1635, 341138 → 1330 |
| `tests/test_storage.py` | 36, 40, 41, 82, 83, 99, 100, 114 | store (v1) | 850302 → 1635 |
| `tests/test_store_examples.py` | 25, 64, 70, 71 | store-judge (v1) | 850302 → 1635 |
| `tests/test_store_upsert.py` | 29, 40, 69, 74, 75 | upsert (v3) | 850302 → 1635, 850330 → 1635 |
| `contour.yaml` | 189, 192, 233, 249, 252, 274, 281, 284, 285 | human | done in this commit |

Live vs literal: `test_score_examples`, `test_cli`, `test_harvest_e2e`,
`test_storage` compute the score through `score_expertise` (red until
`processors.py` changes); `test_store_examples`, `test_store_upsert` hold it
as a literal (green either way — they are updated so no file keeps 850302).

Left as history: `docs/TASK_MEGATRON*.md` (v1–v4), `decks/*.json`,
`.morph/runs/*`.

## 3. Acceptance

Test baseline: **80** (`80 passed`, master `6db8f39`, 2026-09-28). Runner
`venv/bin/python -m pytest`, value comparisons → `--tb=short`. Every card's
chain, in this order:

```sh
# 0. forensic snapshot, first link (regenerations expected in this deck)
D=/tmp/morph/<card>; mkdir -p $D; S=$(date +%s)
cp <each target> $D/<i>-$S.py
(
 set -e
 # 1. syntax, 3.9
 venv/bin/python -c "import ast,sys; [ast.parse(open(f).read(), f, feature_version=(3,9)) for f in sys.argv[1:]]" <targets>
 # 2. own test file(s)
 venv/bin/python -m pytest <own tests> -q --tb=short
 # 3. prose + deletion + envelope + old-value guard, per target
 venv/bin/python decks/v5_guard.py <file> --quotes Q --hashes H --tests T --lines <§2.5 lines> --max 60
 # 4. mutants (live cards only), temp copy of megatron/ and tests/
 mut megatron/processors.py append:$D/m1.py <own test>     # M1: linear score back
 mut megatron/processors.py append:$D/m2.py <own test>     # M2: weights swapped (score, score-judge)
 # 5. full run minus the live files still owned by other cards
 venv/bin/python -m pytest tests -q --tb=short --ignore=<...>
) > $D/acc.log 2>&1; rc=$?; cat $D/acc.log; exit $rc
```

Guard numbers, measured on the live files before submit:

| file | `"""` (==) | lines with `#` (>=) | `def test_` (==) |
|---|---|---|---|
| `megatron/processors.py` | 4 | 1 | 0 |
| `tests/test_processors.py` | 12 | 0 | 5 |
| `tests/test_score_examples.py` | 12 | 3 | 3 |
| `tests/test_cli.py` | 10 | 8 | 4 |
| `tests/test_harvest_e2e.py` | 10 | 9 | 2 |
| `tests/test_storage.py` | 12 | 4 | 5 |
| `tests/test_store_examples.py` | 10 | 5 | 2 |
| `tests/test_store_upsert.py` | 8 | 4 | 1 |

`decks/v5_guard.py` (committed with this spec) fails with `PROSE GUARD`,
`TEST COUNT`, `DELETION GUARD` (a removed line outside §2.5), `ENVELOPE`
(> 60 added or removed) or `OLD VALUE LEFT` (850302, 850316, 850330, 341138,
the linear formula, the minnow `7`). Run on the untouched tree it reports
exactly the §2.5 lines as `OLD VALUE LEFT` (checked: 2+7+7+1+5+8+4+5).

Mutants are appended to a temp copy of `megatron/processors.py`:

```python
# M1 — linear score back
_m_score = score_expertise
def score_expertise(profile, stats):
    record = _m_score(profile, stats)
    record["expertise_score"] = profile.get("followers", 0) + 2 * stats.get("total_stars", 0)
    return record
# M2 — weights swapped: torvalds 1644, minnow 181
import math as _m_math
_m_score2 = score_expertise
def score_expertise(profile, stats):
    record = _m_score2(profile, stats)
    record["expertise_score"] = round(200 * _m_math.log10(profile.get("followers", 0) + 1) + 100 * _m_math.log10(stats.get("total_stars", 0) + 1))
    return record
```

Examples the tests prove (one assertion each, existing test methods):

- **S.1** torvalds fixtures → `expertise_score` 1635, `primary_language` "C" (`test_processors`, `test_score_examples`).
- **S.2** followers 7, total_stars 0, languages {} → 90, None (same two files).
- **S.3** the whole record equals the expected dict with 1635 (`test_processors` l.63, `test_score_examples` l.102).
- **H.1** `harvest(["torvalds", "minnow"])` → `top_experts` scores `[1635, 90]` (`test_cli`).
- **H.2** harvest over the 3 v2 pages → total_stars 262425, score 1635; msg names 1330 as the single-page value (`test_harvest_e2e`, twice).
- **T.1–T.3** storage: fixture-derived torvalds 1635 saved twice → 1 row; with minnow 100, top 1 is torvalds 1635; upsert A (1635) then B (325474 / 262428 / 1635) → exactly [B].

Final check, by the operator after the run on the run branch:
`venv/bin/python -m pytest tests -q` → `80 passed`, and
`git grep -nE '850302|850316|850330|341138' -- megatron tests contour.yaml` → empty.

## 4. Constraints

1. Edits only; no new file under `megatron/` or `tests/`. Envelope per file
   ≤ 60 added / ≤ 60 removed, removed lines only from §2.5 (hard; a card that
   does not fit is split, the slice is not widened).
2. Python 3.9 syntax, stdlib only (`math`).
3. Code and its unit test in one card (`processors.py` + `test_processors.py`).
   Every judge test of an earlier deck is patched by its own card with intent
   `patch`, never regenerated from scratch.
4. One file — one owner card. The four live test files cannot go green before
   `processors.py` changes, so they wait one generation; each card's full run
   ignores the live files owned by other cards of the deck, and the whole-suite
   check is the operator's (§3, final check).
5. Every patch card's instruction carries "preserve all existing docstrings and
   comments verbatim" — the §2.5 lines are the only exception, and only their
   old number/formula changes.
6. No network in tests; no fixture edited.

## 5. Techniques that have already worked

- Forensic snapshot + subshell `rc` idiom (v4 cards, `.morph/runs/20260928-135849-f40fb5c6/deck.json`).
- Mutants by appending a redefinition (v4: 0 of 5 survivors).
- Prose guard with the count taken from the live file (v4 lesson: glm dropped
  a docstring line of `cli.py`, −1, invisible to tests).
- **New:** a deletion guard — removed lines must be a subset of named line
  numbers; turns "don't rewrite" from a wish into a check.

## 6. What is intentionally NOT specified

Card breakdown, slices, message wording of the updated `msg=` strings (they
must name the new value), where `import math` goes.

## 7. Out of scope

- **Retry / backoff** — `smoke-v4-big.log`: 60/60 logins saved, zero refusals;
  no refusal artifact, same reason as v2–v4 §7.
- **Migrating stored scores in `experts.db`** — the 63 rows keep the linear
  value; re-harvesting is cheaper than a migration.
- Any real network call in tests or acceptance.
- New scoring features: weights as parameters, per-language scores, recency,
  normalisation to 0–100, tie-breaking in `top_experts` (A and B of the upsert
  test now tie at 1635; the test still tells them apart by followers/stars).
- `int()` vs `round()`: every control value has a fractional part below 0.31,
  so truncation and rounding agree and the tests cannot tell them apart; the
  formula says `round`, and a rounding-sensitive example would be a new
  feature of the test set.
- Editing old specs, decks and run archives that quote 850302.

## 8. How to run

```bash
cd ../MorphProject/mrph && set -a; source ../morph-lab/.env; set +a
R=/home/john/Documents/Work2026/Megatron        # absolute: relative --root commits nothing (v3 §11)
venv/bin/mrph deck clear --root $R && venv/bin/mrph deck reset --root $R
venv/bin/mrph deck add --root $R --file $R/decks/v5.json
venv/bin/mrph deck check --root $R
venv/bin/mrph run --root $R --processor glm --route sync --max-regenerations 9
```

Ceiling **$5** (v4: $0.00826 for 3 requests).

## 9. Pre-registration of predictions

| quantity | prediction |
|---|---|
| cards | 7 |
| generations | 2 |
| provider bill | < $0.05 |
| cards with regeneration | 1–3 (first patch deck: docstring edits vs. the guard) |
| mutants surviving | 0 of 7 (M1 ×5, M2 ×2) |
| lines removed, whole deck | ≤ 40 (the §2.5 set, `processors.py` import line included) |
| `"""` counts | unchanged in all 8 files |
| tests at the end | 80 |

**Falsifiable claim:** 7/7 written, every removed line is in §2.5, and the
final check prints `80 passed` with no old value left in `megatron/`,
`tests/` or `contour.yaml`.

## 10. What to record at the end

Cards written/failed/skipped, attempts per card, regeneration causes (from
`/tmp/morph/<card>/`), wall time per generation, provider bill, per-file
numstat, final test count, mutant kill table.

## 11. Actual

Two runs, processor `glm` (z-ai/glm-5.3-flash, sync), `--root` absolute.

- `20260928-143742-4e753d5e` (deck `v5.json`, 7 cards, 2 generations, ~1 min):
  6 written, **score-judge-v5 failed** (3 attempts, all rejected by the
  syntax gate: line 128 of 126, then line 1 twice). cli-v5 and storage-v5
  passed on attempt 2 after the same kind of rejection (line 145 of 143, 151 of
  149). $0.01384, 11 requests.
- `20260928-145156-59f4a062` (deck `v5-rerun.json`: score-judge-v5 alone,
  `variants: 2`, plus the line "exactly ONE fenced python block ... no second
  fenced block, no prose"): v1 cut off (unclosed fence), **v2 written**.
  $0.00211, 2 requests.

| quantity | prediction | actual |
|---|---|---|
| cards | 7 | 7 written (6 + 1 on the rerun) |
| generations | 2 | 2 + 1 (rerun) |
| provider bill | < $0.05 | **$0.01595** (13 requests) |
| cards with regeneration | 1–3 | **3** (cli, storage: 1 each; score-judge: 2 + a rerun) |
| mutants surviving | 0 of 7 | **0 of 7** |
| lines removed, whole deck | ≤ 40 | **39** (all from the §2.5 lists; `processors.py` −2, the import was added, not replaced) |
| `"""` counts | unchanged | unchanged in all 8 files |
| tests at the end | 80 | **80 passed**; `git grep` of the old values in `megatron tests contour.yaml`: empty |

**Falsifiable claim — held, with one rerun:** 7/7 written, every removed line
is in §2.5, 80 passed, no old value left.

Findings:

1. **All 6 rejections were syntax-gate rejections, and the forensic snapshot
   caught none of them.** The gate runs before acceptance, restores the file
   and drops the answer, and sync results live only in memory, so
   `/tmp/morph/score-judge-v5/` was never created. The cause cannot be
   recovered. The hypothesis is a second fenced block glued in by
   `response_to_file_body`, which joins every block (errors at the last line + 2
   and at line 1). It is consistent with, but not proven by, the rerun: with the
   one-block line, v1 came back with an unclosed fence and v2 was clean.
2. **`variants: 2` on a single-target card leaves a copy in the tree:**
   `tests/test_score_examples.score-judge-v5.v2.py` (identical to the winner)
   was committed with the card and breaks pytest collection (module name with
   dots). The rerun's acceptance ignored it by `--ignore-glob`; the copy was
   removed by hand in `c9af809`.
3. The deletion guard (removed lines ⊆ named line numbers) never fired on a
   written answer: every answer that got past the syntax gate was a clean
   in-place edit.
