# TASK: PaukMegatron v6 — resilient collection: partial discover, `harvest --skip-existing`

Spec per `TASK_TEMPLATE.md` (mrph). Record: `contour.yaml` (Harvest, Discover
Logins, Store Experts), updated by hand in the same commit as this spec.
Previous specs `docs/TASK_MEGATRON.md`, `_V2.md` … `_V5.md` are history and
are not edited.
Executor: Morph, processor `glm` (z-ai/glm-5.3-flash, route sync).

Touch points were named by the scout (`mrph scout --seed-from-primer`, run
`20260928-142719-942e103e`, ref `f2e76c0`, $0.0200), then verified by line.

## 1. Why this

Scale probe of 2026-09-28 (operator's measurement; artifact `logins-1k.txt`,
commit `ada2619`): four `discover` queries aimed at **~1230** logins. The
**36th** search request (page 6 of a query) got HTTP **403**;
`GitHubError: HTTP 403` escaped as an **unhandled traceback** from
`search.discover_logins` (`megatron/search.py:90`) through `cli.main`
(`megatron/cli.py:59`). Logins in hand: **747**; **~483** lost together with
the pages already fetched for the dying query. There is no resume: a repeat
costs **~40 search + ~1500 core** requests, and the `harvest` over the 747
already saved would fetch every one of them again.

Two numbers this deck is judged by:

- a `GitHubError` on page N of `discover` costs **0** already-fetched logins:
  pages 1…N−1 are printed, exit code **3**, no traceback;
- `harvest --skip-existing` over a list whose logins are already in the db
  makes **0** requests for them.

## 2. Contract

### 2.1. INPUT shapes with addresses

| shape | defined at |
|---|---|
| `GitHubError(message, status)`, `.status` int | `megatron/github_client.py:61` — our own `Exception` subclass, constructed directly: `GitHubError("HTTP 403 for " + url, 403)` |
| transport `transport(url, headers) -> (status, headers_dict, body_bytes)` | `megatron/github_client.py:46` (`urllib_transport`); `GitHubClient(token="x", transport=fake)` at `:70`. `fetch_json` runs it in an executor: an exception the transport **raises** propagates out of `fetch_json` unchanged; a returned status >= 400 becomes `GitHubError` (`:120`) |
| discover result `{"logins", "total_count", "incomplete_results", "pages"}` | `megatron/search.py:104` |
| search fixtures `search_page1/2.json` + `.headers.txt` (page 1 → Link next to page 2; `total_count` 1230) | `tests/fixtures/`, loaders `load_body`/`load_headers`/`make_fake` in `tests/test_search.py:25-66` |
| fake `fetch_json(path)` for harvest (torvalds from fixtures, minnow = torvalds copy with followers 7, repos `[]`) | `tests/test_cli.py:25` `make_fake`, `:47` `make_failing_fake` |
| CLI transport patching: `mock.patch("megatron.github_client.urllib_transport", fake)` before `main(argv)` | `tests/test_cli_discover.py:66` |
| Expert Record, `save_experts(db_path, records)`, schema `experts(login TEXT PRIMARY KEY, …)` | `megatron/storage.py:7, :30` |

**Synthetic search walk** (for pages beyond the two fixtures; construct, do not
add a fixture file). Query `Q = "followers:>5000"`, `U1` as in
`tests/test_search.py:14`. Page k (1-based) is requested at `U1` for k = 1 and
at `U1 + "&page=%d" % k` otherwise; its response is status 200, headers
`{"Link": '<' + U1 + '&page=%d>; rel="next"' % (k + 1)}`, body
`{"total_count": 240, "incomplete_results": false, "items": [{"login": "p%d_u%02d" % (k, i)} for i in range(30)]}`.
The fake counts its calls and on call number N **raises**
`GitHubError("HTTP 403 for " + url, 403)` instead of answering.

### 2.2. OUTPUT shapes

**discover result.** Unchanged on full success (the four keys, exactly — D.1–D.3
compare the whole dict). On a `GitHubError` while fetching page N the result
carries **two more keys**:

```
{"logins": <logins of pages 1..N-1, API order>, "total_count": <from page 1, None if N == 1>,
 "incomplete_results": <as before, over pages 1..N-1>, "pages": N - 1,
 "failed_page": N, "failed_status": <GitHubError.status>}
```

No request is made after the failing one. The client's transport is restored
(the `finally` stays). Only `GitHubError` is caught; any other exception
(`ValueError` for pages < 1, a transport raising `RuntimeError`, bad JSON)
propagates as today.

**harvest result.** `harvest(logins, fetch_json, db_path, concurrency=10, skip_existing=False)`.
With `skip_existing=False` the result is the three-key dict of today, exactly
(B.1/B.2 compare it). With `skip_existing=True` it has a fourth key:
`{"requested": len(logins), "saved": n, "failed": [...], "skipped": [logins found in the db, input order]}`;
skipped logins are not passed to `collect_profiles`; if nothing is left to
fetch, `collect_profiles` is not called at all.

**CLI.**

| command | stdout | stderr | exit |
|---|---|---|---|
| `discover`, full success | logins, one per line (unchanged) | `discovered {n} of {total}, pages {p}` (+ `warning: incomplete_results`), unchanged | 0 |
| `discover`, GitHubError on page N | logins of pages 1…N−1 | the summary line as above with `pages N-1`, plus `warning: partial result, page {N} failed: HTTP {status}`; no `Traceback` | **3** |
| `harvest [--skip-existing]` | `saved {saved} of {requested} -> {db}` (unchanged), then **new** `fetched {f}, skipped {s}, failed {x}` — printed always, `skipped 0` without the flag | `failed: {login}` per failure (unchanged) | 0 / 1 (unchanged: 1 iff any failed) |

`fetched` = logins passed to `collect_profiles` (= requested − skipped).

### 2.3. Names

- `search.discover_logins` — keys `failed_page`, `failed_status`.
- `storage.existing_logins(db_path) -> set` — the set of `login` values in
  `experts`; a db without the table (fresh path, empty file) gives `set()`,
  never raises for that, never writes rows.
- `cli.harvest(..., skip_existing=False)`; CLI flag `--skip-existing`
  (`store_true`) on the `harvest` subcommand; key `skipped`.
- Exit code **3** = partial discover. `0` full success, `1` harvest with a
  failed login (unchanged).
- stderr line `warning: partial result, page {N} failed: HTTP {status}`;
  stdout line `fetched {f}, skipped {s}, failed {x}`.

### 2.4. What must not break

All **80** tests green. The only existing test whose meaning changes is
`tests/test_search.py` D.5 (lines 244–252 assert that `GitHubError` 404 on an
unrouted page 2 propagates — the behaviour this deck removes); it is
rewritten to the partial result, test count of that file stays **12**. Every
other existing test is untouched; new tests go into new files. No fixture is
edited or added.

### 2.5. Touch points (scout, verified by line)

| file | may remove / rewrite lines | adds | primer owner |
|---|---|---|---|
| `megatron/search.py` | 15 (import `GitHubError`), 84–109 (page loop, result) | docstring sentence on partial result | search (v4) |
| `megatron/storage.py` | none | `existing_logins` | store (v1) |
| `megatron/cli.py` | 17–37 (`harvest`), 59–70 (discover branch), 77–83 (harvest tail) | `--skip-existing` argument | cli, cli-discover |
| `tests/test_search.py` | 236–252 (D.5) | — | search (v4) |
| `contour.yaml` | Harvest, Discover Logins, Store Experts examples | — | human, this commit |

Every docstring and comment outside these ranges stays byte for byte.

## 3. Acceptance

Baseline **80 passed** (master `ada2619`, 2026-09-28). Runner
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
 venv/bin/python -m pytest <own test files> -q --tb=short
 # 3. prose + deletion + envelope guard, per patched file (decks/v6_guard.py)
 # 4. mutants on a temp copy of megatron/ tests/ decks/ — each must turn the own tests red
 # 5. full run
 venv/bin/python -m pytest tests -q --tb=short
) > $D/acc.log 2>&1; rc=$?; cat $D/acc.log; exit $rc
```

Guard numbers, measured on the live files (the guard run on the untouched tree
prints `guard ok` for all four):

| file | `"""` (>=) | lines with `#` (>=) | `def test_` | `--lines` |
|---|---|---|---|---|
| `megatron/search.py` | 10 | 9 | 0 | `15,84-109` |
| `megatron/storage.py` | 6 | 2 | 0 | none |
| `megatron/cli.py` | 6 | 2 | 0 | `17-37,59-70,77-83` |
| `tests/test_search.py` | 26 | 7 | == 12 | `236-252` |

Envelope `--max 60` (added and removed, each) for every patched file.
New test files: `def test_` count >= the number of examples they own (below).

Mutants, appended to the temp copy (a redefinition shadows the real function):

```python
# M-S1 (search.py) — the error escapes again
from megatron.github_client import GitHubError as _m_GE
_m_disc = discover_logins
async def discover_logins(client, query, pages, per_page=30):
    result = await _m_disc(client, query, pages, per_page)
    if "failed_page" in result:
        raise _m_GE("HTTP %d" % result["failed_status"], result["failed_status"])
    return result
# M-S2 (search.py) — collected logins dropped on failure
_m_disc2 = discover_logins
async def discover_logins(client, query, pages, per_page=30):
    result = await _m_disc2(client, query, pages, per_page)
    if "failed_page" in result:
        result["logins"] = []
    return result
# M-S3 (search.py) — failed page reported off by one
_m_disc3 = discover_logins
async def discover_logins(client, query, pages, per_page=30):
    result = await _m_disc3(client, query, pages, per_page)
    if "failed_page" in result:
        result["failed_page"] -= 1
    return result
# M-T1 (storage.py) — nothing is ever found
def existing_logins(db_path):
    return set()
# M-T2 (storage.py) — raises on a db without the table
def existing_logins(db_path):
    import sqlite3 as _m_sql
    conn = _m_sql.connect(db_path)
    try:
        return {row[0] for row in conn.execute("SELECT login FROM experts")}
    finally:
        conn.close()
# M-C1 (cli.py) — partial discover reported as success
_m_main = main
def main(argv=None, fetch_json=None):
    code = _m_main(argv, fetch_json)
    return 0 if code == 3 else code
# M-C2 (cli.py) — --skip-existing ignored
_m_harvest = harvest
async def harvest(logins, fetch_json, db_path, concurrency=10, skip_existing=False):
    result = await _m_harvest(logins, fetch_json, db_path, concurrency)
    result["skipped"] = []
    return result
```

Examples the tests prove:

**Search level** (`discover_logins` with `GitHubClient(token="x", transport=fake)`):

- **P.1** (rewritten D.5, `tests/test_search.py`) fixture page 1 routed, page 2
  unrouted (fake returns 404), pages=2 → result equals
  `{"logins": L1, "total_count": 1230, "incomplete_results": False, "pages": 1, "failed_page": 2, "failed_status": 404}`;
  transport called `[U1, U2]`; `client.transport` is the original fake afterwards.
- **P.2** synthetic walk, raise on call 6, pages=8 → logins `p1_u00 … p5_u29`
  (150, in order), `total_count` 240, `pages` 5, `failed_page` 6,
  `failed_status` 403; exactly 6 transport calls; transport restored.
- **P.3** synthetic walk, raise on call 1 → logins `[]`, `total_count` None,
  `pages` 0, `failed_page` 1, `failed_status` 403.
- **P.4** a transport that raises `RuntimeError` on call 2 → `RuntimeError`
  propagates out of `discover_logins`; transport restored.
- **P.5** synthetic walk without a failure, pages=3 → the four-key dict, no
  `failed_page` key.

**Storage:**

- **T.1** `existing_logins(<fresh temp path>)` → `set()`.
- **T.2** after `save_experts` of torvalds and minnow records →
  `{"torvalds", "minnow"}`; saving torvalds again leaves it the same set.

**CLI** (`main(argv, fetch_json=...)` for harvest; `urllib_transport` patched
for discover):

- **R.1** synthetic walk, raise on call 6, `discover followers:>5000 --pages 8`
  → exit 3; stdout = the 150 logins, one per line; stderr contains
  `discovered 150 of 240, pages 5` and
  `warning: partial result, page 6 failed: HTTP 403`, no `Traceback`.
- **R.2** raise on call 1 → exit 3, stdout empty, stderr contains
  `warning: partial result, page 1 failed: HTTP 403`.
- **R.3** synthetic walk, no failure, `--pages 3` → exit 0, 90 logins, stderr
  has no `partial`.
- **R.4** the motive itself, in a real process: `subprocess.run([sys.executable,
  "-c", <script>], cwd=<repo root>, capture_output=True)` where the script
  replaces `megatron.github_client.urllib_transport` with the synthetic-walk
  fake raising 403 on call 2, then `sys.exit(main(["discover",
  "followers:>5000", "--pages", "3"]))` → `returncode == 3`; the process's
  stderr has no `Traceback` and contains `page 2 failed: HTTP 403`; stdout is
  the 30 logins of page 1. No network: the fake lives inside the child.
- **K.1** db pre-seeded by `harvest(["torvalds"], make_fake(), db)`; then
  `main(["harvest", "torvalds", "minnow", "--db", db, "--skip-existing"], fetch_json=recording_fake)`
  → exit 0; stdout contains `saved 1 of 2` and `fetched 1, skipped 1, failed 0`;
  no fetched path contains `torvalds`; db holds 2 rows.
- **K.2** both pre-seeded, `--skip-existing` → exit 0; fetch_json never
  called; stdout `saved 0 of 2` and `fetched 0, skipped 2, failed 0`.
- **K.3** torvalds pre-seeded, **no** flag → both fetched;
  `fetched 2, skipped 0, failed 0`.
- **K.4** torvalds pre-seeded, `--skip-existing`, `make_failing_fake()` → exit
  1; `fetched 1, skipped 1, failed 1`; stderr `failed: minnow`.
- **K.5** fresh db path, `--skip-existing` → `fetched 2, skipped 0, failed 0`,
  exit 0.
- **K.6** `harvest(["torvalds", "minnow"], make_fake(), db, skip_existing=True)`
  with torvalds pre-seeded → `{"requested": 2, "saved": 1, "failed": [], "skipped": ["torvalds"]}`.

Mutant kill table (who must go red):

| mutant | red in |
|---|---|
| M-S1, M-S2, M-S3 | search card's own tests; the judge test |
| M-T1, M-T2 | storage card's own tests; M-T1 also the cli card's and the judge's |
| M-C1, M-C2 | cli card's own tests; the judge test |
| M-S1 | also the cli card's own tests (R.1, R.4) |

Final check, by the operator on the run branch: `venv/bin/python -m pytest
tests -q` → **80 + the new tests, all passed**, and `git diff --stat
master -- tests/fixtures` empty.

## 4. Constraints

1. Python 3.9 syntax, stdlib only. No network in tests or acceptance.
2. Patched files: envelope ≤ 60 added / ≤ 60 removed per file, removed lines
   only from §2.5 (hard; a card that does not fit is split, the slice is not
   widened). Pure new logic goes to the new function in `storage.py`, the
   CLI gets only wiring.
3. Code and its unit tests in one card. New tests in new files; the only
   existing test edited is D.5.
4. One file — one owner card per generation; a file a card writes is not in the
   context slice of a card in the same generation.
5. Every patch card's instruction carries "preserve all existing docstrings and
   comments verbatim" and "exactly ONE fenced block per file, no second block,
   no prose" (v5 §11 finding 1).
6. `GitHubError` is caught only in `discover_logins`, only around the page
   fetch. `cli.main` does not wrap anything in a broad `try/except`.

## 5. Techniques that have already worked

- Forensic snapshot + subshell `rc` idiom (v4, v5).
- Mutants by appending a redefinition (v4: 0 of 5 survivors, v5: 0 of 7).
- Deletion guard: removed lines ⊆ named line numbers (v5; generalised to
  ranges and additions-only in `decks/v6_guard.py`).
- Prose guard with the count taken from the live file (v4 lesson: glm dropped
  a docstring line of `cli.py`, −1, invisible to tests).
- One-fenced-block line in the instruction (v5 rerun).

## 6. What is intentionally NOT specified

Card breakdown, context slices, names of the new test files and helpers, how
`existing_logins` handles the absent table (create-if-absent or catch), where
the new stderr line is printed relative to the summary, docstring wording.

## 7. Out of scope

- **Retry / backoff / Retry-After** on 403/429 — hard. The verbatim 403
  artifact (body + headers of the refused response) has not been captured;
  a retry policy built without it is a guess. Once captured — a separate deck.
- Resume of `discover` from a page (the `failed_page` key makes it possible
  later; no `--start-page` now).
- Parallel `discover`, token pools, rotation.
- Migrations of `experts.db`; `existing_logins` only reads.
- De-duplication of the login list passed to `harvest`; `--skip-existing`
  treats the db as of the start of the call.
- Catching `GitHubError` anywhere but the discover page loop; any real network
  call in tests or acceptance.
- Editing old specs, decks and run archives.

## 8. How to run

```bash
cd ../MorphProject/mrph && set -a; source ../morph-lab/.env; set +a
R=/home/john/Documents/Work2026/Megatron        # absolute: relative --root commits nothing (v3 §11)
venv/bin/mrph deck clear --root $R && venv/bin/mrph deck reset --root $R
venv/bin/mrph deck add --root $R --file $R/decks/v6.json
venv/bin/mrph deck check --root $R
venv/bin/mrph run --root $R --processor glm --route sync --max-regenerations 9
```

Ceiling **$5** (v5: $0.01595 for 13 requests).

## 9. Pre-registration of predictions

| quantity | prediction |
|---|---|
| cards | 4 |
| generations | 3 |
| provider bill | < $0.05 |
| cards with regeneration | 1–2 |
| mutants surviving | 0 of 12 kill checks |
| tests at the end | 80 + 14…24 |
| removed lines outside §2.5 | 0 |
| files in `.morph/rejected/` | = number of syntax-gate rejections in the run log |

**Falsifiable claim:** 4/4 written, every removed line is in §2.5, the full run
is green with at least 94 tests, 0 mutant survivors.

## 10. What to record at the end

Cards written/failed/skipped, attempts per card, regeneration causes (from
`/tmp/morph/<card>/` and `.morph/rejected/`), wall time per generation,
provider bill, per-file numstat, final test count, mutant kill table.
