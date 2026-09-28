# TASK: PaukMegatron v3 — close three measured coverage holes

Spec per `TASK_TEMPLATE.md` (mrph). Record: `contour.yaml` (Store Experts
example 3, GitHub Client example 3, Collect Profiles example 4). Previous
specs and their actuals: `docs/TASK_MEGATRON.md`, `docs/TASK_MEGATRON_V2.md`.
Executor: Morph, processor `glm` (z-ai/glm-5.3-flash, route sync).

## 1. Why this

External verification of v2 (`VERIFY_RUNBOOK.md`) caught **20 of 24**
mutations. Of the 4 that escaped, **3 are in scope** of shipped behaviour and
each is a property the spec promises but no test observes. Re-measured
2026-09-28 on master `1491467`, each mutant against the **full** suite:

| # | property promised | where | mutant | full suite on mutant |
|---|---|---|---|---|
| 1 | `save_experts` upserts by login | `megatron/storage.py:42-54` | `INSERT INTO … ON CONFLICT(login) DO UPDATE …` → `INSERT OR IGNORE INTO …` (upsert clause removed) | **56 passed** |
| 2 | status ≥ 400 → `GitHubError` | `megatron/github_client.py:120` | `if status >= 400:` → `if status > 400:` | **56 passed** |
| 3 | at most `concurrency` logins in flight | `megatron/collectors.py:26,30` | `async with semaphore:` → `if True:` | **56 passed** |

Why they escape: (1) the only upsert test (`tests/test_store_examples.py`,
Store Experts example 1) saves the **same** record twice and counts rows —
an ignored second insert also leaves 1 row; (2) the only error test uses 404,
not the boundary; (3) no fake fetcher counts in-flight calls, so a removed
semaphore changes nothing visible.

Hole 1 is not hypothetical: a real re-harvest changes the row. The torvalds
record built from the 2026-09-28 fixtures has `followers` 325466,
`total_stars` 262418, `expertise_score` 850302; the smoke run of
2026-09-28 12:58 (`smoke-v2.log`: `saved 5 of 5 -> experts.db`) stored
325474 / 262428 / 850330 for the same login. Under mutant 1 a second
harvest keeps the stale row silently.

The number this deck is judged by: **each of the 3 mutants (plus one
sibling mutant each for holes 1 and 3) makes at least one new test red**,
and all 56 existing tests stay green.

## 2. Contract

### 2.1. INPUT shapes with addresses

| shape | defined at |
|---|---|
| Expert Record | `contour.yaml` → `dataObjects` → Expert Record; a live example is below |
| `save_experts(db_path, records) -> int`, `top_experts(db_path, n=10)` | `megatron/storage.py:30`, `:77` |
| `GitHubClient`, `GitHubError(.status)`, Transport `(url, headers) -> (status, headers, body)` | `megatron/github_client.py:61`, `:78`, `:99`; transport contract: `docs/TASK_MEGATRON_V2.md` §2.1 |
| fake transport idiom, `USER_URL` | `tests/test_github_client.py:52` (`fake_transport(routes)`), `:198-207` (A example 6, the 404 test) |
| `collect_profiles(logins, fetch_json, concurrency=10)` | `megatron/collectors.py:15`; semaphore `:26`, acquired `:30` around both fetches of one login |
| GitHub user JSON / repos JSON | `tests/fixtures/user_torvalds.json`, `tests/fixtures/repos_torvalds.json` (verbatim) |
| 5 search logins | `tests/fixtures/search_users_python.json` `items[*].login`: karpathy, openai, google, huggingface, rafaballerini |

**Record A** — torvalds, built from the fixtures (`parse_user_profile` +
`parse_repo_stats` + `score_expertise` over `user_torvalds.json` and
`repos_torvalds.json`), verbatim:

```json
{"login": "torvalds", "id": 1024025, "name": "Linus Torvalds",
 "company": "Linux Foundation", "location": "Portland, OR",
 "followers": 325466, "public_repos": 12, "created_at": "2011-09-03T15:26:22Z",
 "total_stars": 262418, "languages": {"C": 8, "OpenSCAD": 1},
 "expertise_score": 850302, "primary_language": "C"}
```

**Record B** — the same login as stored by the live smoke run
(`experts.db`, 2026-09-28 12:58): Record A with exactly three fields
substituted — `followers` **325474**, `total_stars` **262428**,
`expertise_score` **850330**.

Status **400** in example S.1 is the boundary itself, not an observed
response; the body is A example 6's literal `b'{"message": "Not Found"}'`,
headers `{}`. Numbers are never invented beyond that.

### 2.2. OUTPUT shapes

None new. `top_experts` returns Expert Records exactly as in v1; tests
compare whole dicts.

### 2.3. Names

| file | proves |
|---|---|
| `tests/test_store_upsert.py` | U.1 |
| `tests/test_client_status_boundary.py` | S.1 |
| `tests/test_collect_concurrency.py` | K.1, K.2 |

No file under `megatron/` changes. Tests import the code under test at call
time via the module (`from megatron import storage` / `collectors`,
`megatron.github_client.GitHubClient`) so that a mutated copy is what runs.

### 2.4. What must not break

All 56 existing tests green and unmodified; every file under `megatron/` and
every existing file under `tests/` byte for byte; fixtures read-only.

## 3. Acceptance

Test baseline at task time: **56**. Runner `venv/bin/python -m pytest`.
Value comparisons → `--tb=short`, `maxDiff = None` in every test class.
Stepped, narrow first. A mutant is applied to a temp copy of `megatron/`
and `tests/`; the acceptance fails if the mutant did not apply **or** the
new test passes on it.

```bash
# 0. syntax, each new test file
venv/bin/python -c "import ast,sys; [ast.parse(open(f).read(), f, feature_version=(3,9)) for f in sys.argv[1:]]" <test file>

# mutation helper (inline in each acceptance)
R=$PWD; mut() {  # $1 file, $2 sed script, $3 test file
  T=$(mktemp -d); cp -r megatron tests $T/; sed -i "$2" $T/$1
  cmp -s $1 $T/$1 && { echo "MUTANT NOT APPLIED: $2"; exit 1; }
  (cd $T && $R/venv/bin/python -m pytest $3 -q --tb=no -p no:cacheprovider) && { echo "MUTANT SURVIVED: $2"; exit 1; }
  echo "mutant killed: $2"; }

# U. upsert
venv/bin/python -m pytest tests/test_store_upsert.py -q --tb=short
mut megatron/storage.py 's/"INSERT INTO experts ("/"INSERT OR IGNORE INTO experts ("/; /ON CONFLICT(login) DO UPDATE SET/,/primary_language=excluded.primary_language",/c\                "",' tests/test_store_upsert.py
mut megatron/storage.py '/ON CONFLICT(login) DO UPDATE SET/,/primary_language=excluded.primary_language",/c\                "ON CONFLICT(login) DO NOTHING",' tests/test_store_upsert.py

# S. status boundary
venv/bin/python -m pytest tests/test_client_status_boundary.py -q --tb=short
mut megatron/github_client.py 's/if status >= 400:/if status > 400:/' tests/test_client_status_boundary.py

# K. concurrency
venv/bin/python -m pytest tests/test_collect_concurrency.py -q --tb=short
mut megatron/collectors.py 's/async with semaphore:/if True:/' tests/test_collect_concurrency.py
mut megatron/collectors.py 's/asyncio.Semaphore(concurrency)/asyncio.Semaphore(concurrency + 1)/' tests/test_collect_concurrency.py

# regression: full run, then guards
venv/bin/python -m pytest tests -q --tb=short
git diff --quiet HEAD -- megatron tests/fixtures || { echo "GUARD FAILED: megatron/ or fixtures modified"; exit 1; }
! grep -n "urlopen" tests/*.py || { echo "GUARD FAILED: a test calls urlopen"; exit 1; }
```

Examples each test must prove:

**U. Store upsert** — fresh temp db.
1. `save_experts(db, [A])` → 1; `save_experts(db, [B])` → 1; the table has
   exactly 1 row; `top_experts(db, 10) == [B]` (whole-dict equality,
   `languages` decoded) — so `followers` 325474, `total_stars` 262428,
   `expertise_score` 850330.

**S. Status boundary** — real `GitHubClient(token="x", transport=fake)`.
1. Fake transport answers `https://api.github.com/users/torvalds` with
   `(400, {}, b'{"message": "Not Found"}')` → `fetch_json("/users/torvalds")`
   raises `GitHubError`, `.status == 400`; the transport was called exactly once.

**K. Concurrency observed** — the 5 search logins; fake async `fetch_json`
serves a deep copy of parsed `user_torvalds.json` for `/users/<login>` and of
`repos_torvalds.json` for `/users/<login>/repos?per_page=100`. On entry it
increments an `in_flight` counter and records `peak = max(peak, in_flight)`,
then `await asyncio.sleep(0.01)`, then decrements (in `finally`) and returns.
1. `concurrency=2` → `peak == 2`; 5 results, none `None`; the fake called 10 times.
2. `concurrency=1` → `peak == 1`; 5 results, none `None`.

## 4. Constraints

1. Every target is a **new test file**; no existing file is edited.
2. Python 3.9-compatible syntax, stdlib only (`unittest`, `asyncio`,
   `sqlite3`, `tempfile`, `json`, `copy`, `os`).
3. The author of the criterion is not the author of the code: code is
   already shipped and not touched; the card writes only its test.
4. One file — one owner card; no card reads a neighbour's target.
5. No test opens a socket; no test sleeps longer than 0.01 s per fake call.

## 5. Techniques that have already worked

- Mutation-gated acceptance (v2 order card: 0 of 2 mutants survived, first attempt).
- Domain fixture = verbatim artifact; Record B is the live row, not a composition.
- Card idiom from `.morph/runs/20260928-123443-4f33236b/deck.json`
  (forensic snapshot, `set -e` subshell, AST 3.9 link).

## 6. What is intentionally NOT specified

Card breakdown, slices, per-card acceptance wording.

## 7. Out of scope

- **Retry / backoff / `Retry-After` / 403 and 429 handling.** No measured
  refusal exists: `smoke-v2.log` (5 logins, live API, 2026-09-28 12:58) is
  one line, `saved 5 of 5 -> experts.db` — 0 failures, 0 refusals; a large
  smoke log (`smoke-v2-big.log`) is **absent** from the project root at spec
  time, so there is no 429/403 body or header to fixture. No number — no
  section. Behaviour stays as v2 §7: status ≥ 400 raises, the next request
  waits on the rate-limit state.
- The 4th escaped mutation of the v2 verification (not named for v3 by
  the operator).
- Any change to `megatron/*.py`, existing tests, fixtures, CLI, README.
- Any real network call in tests or acceptance.

## 8. How to run

```bash
cd ../MorphProject/mrph && set -a; source ../morph-lab/.env; set +a
venv/bin/mrph deck clear --root ../../Megatron && venv/bin/mrph deck reset --root ../../Megatron
venv/bin/mrph deck add --root ../../Megatron --file ../../Megatron/decks/v3.json
venv/bin/mrph deck check --root ../../Megatron
venv/bin/mrph run --root ../../Megatron --processor glm --route sync --max-regenerations 9
```

Ceiling **$5**: at v2's $0.0110 for 5 requests, 9 regenerations bound the
bill two orders of magnitude below it.

## 9. Pre-registration of predictions

| quantity | prediction |
|---|---|
| cards | 3 |
| generations | 1 |
| provider bill | < $0.02 |
| cards with regeneration | ≤ 1 |
| mutants surviving | 0 of 5 |
| tests at the end | 56 + 4 = 60 |

**Falsifiable claim:** all 3 cards `written` within ≤ 2 attempts each, and
all 5 mutants of §3 are red on the accepted tests; re-running the v2
verification's 3 in-scope mutants against the full suite gives 0 survivors.

## 10. What to record at the end

Cards written/failed/skipped, attempts per card, wall time, provider bill,
final test count, mutant kill table, `git log --oneline` of the run branch.

## 11. Actual

_filled in after the run_
