# TASK: PaukMegatron v7 — deterministic order in `top_experts`

Spec per `TASK_TEMPLATE.md` (mrph). Record: `contour.yaml` (Store Experts),
updated by hand in the same commit as this spec. Previous specs
`docs/TASK_MEGATRON.md`, `_V2.md` … `_V6.md` are history and are not edited.
Executor: Morph, processor `glm` (z-ai/glm-5.3-flash, route sync).

Touch points were named by the scout (`mrph scout --seed-from-primer`, run
`20260928-153100-c99e3799`, ref `bd41dd6`, $0.0104, 7 model turns, 6 reads),
then verified by line. The task text given to the scout named no file and no
symbol other than `top_experts`.

## 1. Why this

`top_experts` orders by `expertise_score DESC` only (`megatron/storage.py:88`).
The v5 formula `round(100*log10(followers+1) + 200*log10(total_stars+1))` is
coarse. Measured on `experts.db` (63 rows, followers and total_stars as stored;
the stored `expertise_score` column is still the old linear value — the db was
not rebuilt — so the score was recomputed):

- **14 of 63** experts share **7** score values (7 pairs):
  1668 deepseek-ai/github, 1657 google/huggingface, 1563 ruanyf/mattpocock,
  1532 lucidrains/apple, 1479 peng-zhihui/adrianhajdin, 1430
  antfu/iam-veeramalla, 1341 yyx990803/geohot.
- **Two** of the pairs are inside the top-10 (ranks 4–5 and 7–8).
- The 63 rescored rows saved into a fresh db in stored order and in reverse
  order give top-10 lists that differ in **4 of 10** positions
  (`deepseek-ai, github` ↔ `github, deepseek-ai`; `google, huggingface` ↔
  `huggingface, google`).
- The 14 tied rows saved in three orders (by login, reversed, a fixed shuffle)
  give **three different** `top_experts(db, 14)` lists, **none** equal to the
  order this spec requires.

No pair ties on followers as well, so the third key is proved on synthetic rows.

Number this deck is judged by: the same set of rows gives **1** `top_experts`
list whatever the insertion order.

## 2. Contract

### 2.1. INPUT shapes with addresses

| shape | defined at |
|---|---|
| Expert Record — a dict with exactly the 12 keys of `_COLUMNS`; `languages` a dict | `megatron/storage.py:24` (`_COLUMNS`), schema `:7` |
| `save_experts(db_path, records) -> int` — upsert by login, creates the table | `megatron/storage.py:30` |
| `top_experts(db_path, n=10) -> list of Expert Records` | `megatron/storage.py:77`; the SQL at `:86-90` |

**Base record** for tests (construct; no fixture file, no network). Every
example below builds `dict(BASE, login=..., expertise_score=..., followers=..., total_stars=...)`:

```python
BASE = {"login": None, "id": 1, "name": None, "company": None, "location": None,
        "followers": 0, "public_repos": 1, "created_at": "2011-09-03T15:26:22Z",
        "total_stars": 0, "languages": {"C": 1}, "expertise_score": 0,
        "primary_language": "C"}
```

**The 14 tied rows** (real followers / total_stars from `experts.db`, score by
the v5 formula), listed **in the required order**:

| login | expertise_score | followers | total_stars |
|---|---|---|---|
| deepseek-ai | 1668 | 106580 | 669069 |
| github | 1668 | 87777 | 741208 |
| google | 1657 | 79420 | 684829 |
| huggingface | 1657 | 68981 | 735420 |
| ruanyf | 1563 | 87692 | 220179 |
| mattpocock | 1563 | 46935 | 302613 |
| lucidrains | 1532 | 61572 | 183638 |
| apple | 1532 | 40337 | 226660 |
| peng-zhihui | 1479 | 87445 | 83821 |
| adrianhajdin | 1479 | 37503 | 127554 |
| antfu | 1430 | 40176 | 70446 |
| iam-veeramalla | 1430 | 34295 | 76125 |
| yyx990803 | 1341 | 111510 | 15203 |
| geohot | 1341 | 47400 | 23290 |

### 2.2. OUTPUT shape

`top_experts(db_path, n=10)` returns at most `n` Expert Records ordered by

1. `expertise_score` **DESC**, then
2. `followers` **DESC**, then
3. `login` **ASC**, binary comparison (SQLite's default `BINARY` collation =
   Python's `sorted()` on `str`: `"Bob" < "alice"`).

The order is total (login is the primary key) and does not depend on the order
rows were inserted. The `n` rows returned are the first `n` of that total
order — the tie-break applies **before** the limit, not to the already-cut
list. Everything else is unchanged: `languages` decoded to a dict, the same
12 keys, `n` default 10, no write to the db.

### 2.3. Names

- `megatron.storage.top_experts(db_path, n=10)` — name and signature unchanged.
- Column names `expertise_score`, `followers`, `login` (schema,
  `megatron/storage.py:7`).
- No new public function, no new module-level name is required.

### 2.4. What must not break

All **107** tests green (baseline, master `bd41dd6`). Existing tests that call
`top_experts` (`tests/test_storage.py`, `test_store_examples.py`,
`test_store_upsert.py`, `test_cli.py`, `test_harvest_e2e.py`,
`test_cli_resilience.py`) have no ties on score and keep their meaning. No
existing test and no fixture is edited; new tests go into new files.

### 2.5. Touch points (scout, verified by line)

| file | may remove / rewrite lines | adds | primer owner |
|---|---|---|---|
| `megatron/storage.py` | 79–90 (the `top_experts` docstring 79–82 and the query 83–90) | — | store (v1), store-v6 |
| `contour.yaml` | Store Experts behaviour + 2 examples | — | human, this commit |

The docstring range 79–82 is included on purpose: a card may reword
"highest expertise_score, DESC" and add a sentence on the tie-break (v6 lost
two attempts on a range that did not include the docstring line it extended).
Line 77 (`def`) and 78 (type comment) stay byte for byte, and so does every
line outside 79–90.

Scout named `megatron/storage.py` and `tests/test_storage.py`. The second is
not touched: by §2.4 new tests go into new files.

## 3. Acceptance

Baseline **107 passed** (master `bd41dd6`, 2026-09-28). Runner
`venv/bin/python -m pytest`, value comparisons → `--tb=short`. Chain per card:

```sh
# 0. forensic snapshot, first link
D=/tmp/morph/<card>; mkdir -p $D; S=$(date +%s)
cp <each target> $D/<i>-$S.py 2>/dev/null
(
 set -e
 # 1. syntax, 3.9
 venv/bin/python -c "import ast,sys; [ast.parse(open(f).read(), f, feature_version=(3,9)) for f in sys.argv[1:]]" <targets>
 # 2. own tests
 venv/bin/python -m pytest <own test file> -q --tb=short
 # 3. (storage card) tests of the touched module
 venv/bin/python -m pytest tests/test_storage.py tests/test_store_examples.py tests/test_store_upsert.py tests/test_storage_existing.py -q --tb=short
 # 4. prose + deletion + envelope guard (decks/v6_guard.py)
 # 5. mutants (decks/v7_mut.py) on a temp copy of megatron/ tests/ decks/ — each must turn the own tests red
 # 6. full run
 venv/bin/python -m pytest tests -q --tb=short --ignore-glob='*.v[0-9].py'
) > $D/acc.log 2>&1; rc=$?; cat $D/acc.log; exit $rc
```

Guard numbers, measured on the live file (`guard ok` on the untouched tree):

| file | `"""` (>=) | lines with `#` (>=) | `def test_` | `--lines` | `--max` |
|---|---|---|---|---|---|
| `megatron/storage.py` | 8 | 3 | == 0 | `79-90` | 60 |
| new test files | 0 | 0 | >= 5 | — | — |

Mutants: `venv/bin/python decks/v7_mut.py <name>` prints a self-contained
redefinition of `top_experts` appended to the temp copy of
`megatron/storage.py` (it does not use `_COLUMNS`, so a renamed private name
cannot fake a kill):

| mutant | what it does | killed by (checked against a reference query before the run) |
|---|---|---|
| M-O1 | score only — the v6 behaviour | O.1, O.2, O.3, O.4, O.5 |
| M-O2 | followers key removed (score, login) | O.2, O.3 |
| M-O3 | login key removed (score, followers) | O.3, O.4, O.5 |
| M-O4 | followers ASC | O.1, O.2, O.3 |
| M-O5 | login DESC | O.3, O.4, O.5 |
| M-O6 | `LIMIT` before the tie-break, then sorted in Python | **O.4 only** |
| M-O7 | login `COLLATE NOCASE` | **O.5 only** |

The unmodified v6 code fails every example O.1–O.5 (checked).

Examples the tests prove (each on a fresh db in a `tempfile.TemporaryDirectory`;
"saved in order X" = one `save_experts(db, [...])` call with the records in
that order):

- **O.1** real ties, reverse insertion: the four rows huggingface, google,
  github, deepseek-ai (table §2.1) saved in that order →
  `[r["login"] for r in top_experts(db, 4)] == ["deepseek-ai", "github", "google", "huggingface"]`.
- **O.2** insertion independence: the 14 rows of §2.1, saved into three fresh
  dbs in three orders — sorted by login; that list reversed;
  `random.Random(7).sample(<sorted list>, 14)` — → each
  `top_experts(db, 14)` login list equals the §2.1 table order, so the three
  lists are equal to each other.
- **O.3** third key, synthetic: carol (1000, followers 500), alice (1000, 500),
  bob (1000, 500), zed (1000, 900) saved in that order → `top_experts(db)`
  logins `["zed", "alice", "bob", "carol"]`.
- **O.4** the limit cuts a tie: top (2000, 1), b (1000, 500), a (1000, 500)
  saved in that order → `top_experts(db, 2)` logins `["top", "a"]`.
- **O.5** binary login order: alice (1000, 500), Bob (1000, 500) saved in that
  order → `top_experts(db)` logins `["Bob", "alice"]`.

`total_stars` of the synthetic rows is 0 (BASE); it is not an ordering key.

Final check, by the operator on the run branch: `venv/bin/python -m pytest
tests -q` → **107 + the new tests (>= 10), all passed**; `git diff --stat
master -- tests/fixtures experts.db` empty; no `*.v[0-9].py` file committed.

## 4. Constraints

1. Python 3.9 syntax, stdlib only. No network in tests or acceptance.
2. `megatron/storage.py`: envelope ≤ 60 added / ≤ 60 removed, removed lines
   only from 79–90 (hard). The tie-break lives in the SQL `ORDER BY` (or
   anything else that orders before the limit); `save_experts`,
   `existing_logins`, `_SCHEMA`, `_COLUMNS` are not touched.
3. Code and its unit tests in one card. New tests in new files; no existing
   test is edited.
4. One file — one owner card per generation; a file a card writes is not in the
   context slice of a card in the same generation.
5. Every card's instruction carries "preserve all existing docstrings and
   comments verbatim", "exactly ONE fenced block per file, no second block, no
   prose" (v5) and "the block holds only code — no `---` line, no file path"
   (v6 §11 finding 1: the compiler's `---` framing leaked into the answer).
6. No `variants` on any card: v5 and v6 each committed a
   `<target>.<card>.v2.py` copy that breaks pytest collection. A failed card is
   regenerated, not varied.

## 5. Techniques that have already worked

- Forensic snapshot + subshell `rc` idiom (v4–v6).
- Mutants by appending a redefinition (v4 0/5, v5 0/7, v6 0/12 survivors);
  here generated by `decks/v7_mut.py` so the kill table is checked before the
  run.
- Deletion guard with named ranges, `decks/v6_guard.py` (reused unchanged).
- Real numbers as test data (§2.1 table from `experts.db`), not invented ties.

## 6. What is intentionally NOT specified

Card breakdown, context slices, names of the new test files and helpers,
whether the order is written as one `ORDER BY` or otherwise (as long as it
applies before the limit), docstring wording.

## 7. Out of scope

- Rebuilding or migrating `experts.db` to the v5 formula; the stored
  `expertise_score` column stays as it is, and no test reads `experts.db`.
- Ranking anywhere other than `top_experts`: no CLI output change, no new
  sort in `harvest`, `discover`, `collectors`, `processors`.
- Changing the score formula or its rounding.
- Case-folding or normalising logins.
- An index on the ordering columns.
- Any network in tests or acceptance.
- Editing old specs, decks and run archives.

## 8. How to run

```bash
set -a; source /home/john/Documents/Work2026/MorphProject/morph-lab/.env; set +a
M=~/Documents/python_venv/venv_mrph/bin/mrph
R=/home/john/Documents/Work2026/Megatron        # absolute: relative --root commits nothing (v3 §11)
$M deck clear --root $R && $M deck reset --root $R
$M deck add --root $R --file $R/decks/v7.json
$M deck check --root $R
$M run --root $R --processor glm --route sync --max-regenerations 9
```

Ceiling **$5** (v6: $0.04134 for 12 requests).

## 9. Pre-registration of predictions

| quantity | prediction |
|---|---|
| cards | 2 |
| generations | 2 |
| provider bill | < $0.03 |
| cards with regeneration | 0–1 |
| mutants surviving | 0 of 14 kill checks |
| tests at the end | 107 + 10…16 |
| removed lines outside 79–90 | 0 |
| `*.v[0-9].py` files committed | 0 |

**Falsifiable claim:** 2/2 written, every removed line of `storage.py` is in
79–90, the full run is green with at least 117 tests, 0 mutant survivors, no
variant copy in the tree.

## 10. What to record at the end

Cards written/failed/skipped, attempts per card, regeneration causes (from
`/tmp/morph/<card>/` and `.morph/rejected/`), wall time per generation,
provider bill, per-file numstat, final test count, mutant kill table, and the
scout line: files named / files actually touched / missed / extra.

## 11. Actual
