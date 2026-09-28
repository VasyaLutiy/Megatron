# TASK: PaukMegatron v2 — live GitHub client, repos pagination, `harvest` CLI

Spec per `TASK_TEMPLATE.md` (mrph). Record: `contour.yaml` (groups
`github_client`, `cli`; Collect Profiles example 3; Guardrail
`No Network In Core` revised). v1 spec and its actuals: `docs/TASK_MEGATRON.md`.
Executor: Morph, processor `glm` (z-ai/glm-5.3-flash, route sync).

## 1. Why this

v1 (merged 2026-09-28, 40 tests, $0.0117) is an offline core that **cannot
harvest a single real profile**: nothing in `megatron/` talks to GitHub, and
nothing wires collector → scorer → storage. Two measured defects on top:

- **Pagination.** `collect_profiles` asks for
  `/users/<login>/repos?per_page=100` once. For any user with more than 100
  repos everything past page 1 is silently lost. Measured on torvalds with
  `per_page=5` (fixtures below, fetched 2026-09-28): page 1 alone gives
  `total_stars` **7836**, all 3 pages give **262425** — a single page
  undercounts the score 341138 vs **850316** (−60%).
- **Verification blind spot.** External verification of v1
  (`VERIFY_RUNBOOK.md`, 74 probes, 16/20 mutations caught) found that no
  test — executor's, judge's, or Scenario C's — proves `collect_profiles`
  keeps input order: example 8 feeds the same torvalds fixture to every
  login, so a permutation of the result is invisible unless it moves the
  failing entry. Measured 2026-09-28: a mutant of `collectors.py:42`
  returning `list(reversed(...))` passes **all 40** v1 tests (the failing
  "google" sits at index 2 of 5, the fixed point of a reversal); the
  completion-order mutant (`asyncio.as_completed`) is caught only
  incidentally, by the None-position test (2 of 40 red).

## 2. Contract

### 2.1. INPUT shapes with addresses

| shape | defined at |
|---|---|
| GitHub user JSON | `tests/fixtures/user_torvalds.json` (verbatim) |
| GitHub repos JSON, one page of 100 | `tests/fixtures/repos_torvalds.json` (12 items) |
| **GitHub repos JSON, paginated** | `tests/fixtures/repos_torvalds_page{1,2,3}.json` — verbatim bodies of `/users/torvalds/repos?per_page=5&page={1,2,3}`: 5, 5, 2 items |
| **Response headers of those pages** | `tests/fixtures/repos_torvalds_page{1,2,3}.headers.txt` — verbatim headers (CR stripped): first line `HTTP/2 200`, then one `name: value` per line, split at the first `": "`. The `link` header of page 1 has `rel="next"` → `https://api.github.com/user/1024025/repos?per_page=5&page=2`; page 2 → `...&page=3`; page 3 has no `rel="next"`. Note the path is `/user/1024025/...`, not `/users/torvalds/...`: the client follows the URL verbatim |
| Rate-limit headers | `tests/fixtures/rate_limit_headers.txt` (CRLF; limit 60, remaining 59, reset 1790594886) |
| Search response (5 logins) | `tests/fixtures/search_users_python.json`: karpathy, openai, google, huggingface, rafaballerini |
| Rate Limit State, Expert Profile/Pair/Record | `contour.yaml` → `dataObjects` |
| `parse_rate_limit`, `seconds_to_wait` | `megatron/api_manager.py:11`, `:37` |
| `collect_profiles` | `megatron/collectors.py:15`; the line returning input order is `:42` `return list(await asyncio.gather(*tasks))` |
| `parse_repo_stats`, `score_expertise`, `save_experts`, `top_experts` | `megatron/parsers.py:38`, `megatron/processors.py:6`, `megatron/storage.py:30`, `:77` |

**Transport** (the only seam to the network; tests fake it): a synchronous
callable `transport(url: str, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]`
returning `(status, response_headers, body)`. Header names in the returned
dict are in any case; the client looks them up case-insensitively.

Domain data in tests is a **copy of a fixture**, with at most named fields
substituted (e.g. `login`, `followers`, `x-ratelimit-remaining`). Numbers are
never invented.

### 2.2. OUTPUT shapes

- `GitHubClient.fetch_json(path)` returns the decoded JSON: a dict as is; a
  list **concatenated across all pages** in page order.
- `harvest(...)` returns `{"requested": int, "saved": int, "failed": [login, ...]}`,
  `failed` in input order.
- The `experts` table and Expert Record are unchanged from v1 — no second shape.

### 2.3. Names

| module | public names |
|---|---|
| `megatron/github_client.py` | `API_ROOT = "https://api.github.com"`, `parse_next_link(link_header)`, `urllib_transport(url, headers)`, `class GitHubError(Exception)` with `.status`, `class GitHubClient(token=None, transport=None, sleep=None, clock=None, max_pages=10)` with attributes `token`, `transport`, `rate_limit` and `async fetch_json(path)` |
| `megatron/cli.py` | `async harvest(logins, fetch_json, db_path, concurrency=10)`, `main(argv=None, fetch_json=None) -> int` |
| `megatron/__main__.py` | calls `sys.exit(main())`; nothing else |
| tests | `tests/test_github_client.py`, `tests/test_cli.py`, `tests/test_collect_order.py`, `tests/test_harvest_e2e.py` |

Behaviour of `GitHubClient`:

- `token=None` → `os.environ.get("GITHUB_TOKEN")`, read at construction.
  A truthy token sends `Authorization: Bearer <token>`; otherwise the key
  is absent. Always sent: `Accept: application/vnd.github+json`,
  `User-Agent: megatron`, `X-GitHub-Api-Version: 2022-11-28`.
- `transport=None` → the module-level `urllib_transport`, looked up at
  construction (so `unittest.mock.patch("megatron.github_client.urllib_transport")`
  takes effect). `sleep=None` → `asyncio.sleep` (awaited). `clock=None` →
  `time.time`.
- `fetch_json(path)`: URL is `path` if it starts with `http`, else
  `API_ROOT + path`. **Before every request** (including each page):
  `wait = seconds_to_wait(self.rate_limit, int(clock()))`; if `wait > 0`,
  `await sleep(wait)`. The transport is run off the event loop
  (`run_in_executor`). **After every response**: `parse_rate_limit(headers)`,
  if not None, replaces `self.rate_limit`. Status ≥ 400 → `GitHubError`.
  A list body with a `rel="next"` link is followed until no `next` or
  `max_pages` pages were fetched.
- `urllib_transport`: `urllib.request.urlopen(Request(url, headers=headers), timeout=30)`;
  an `HTTPError` is returned as `(e.code, dict(e.headers), e.read())`, not raised.

`parse_next_link(None)`, `("")` and a header with no `rel="next"` → `None`.

CLI: `python -m megatron harvest <login>... [--db experts.db] [--concurrency 10]`.
`main` with `fetch_json=None` builds `GitHubClient()` and uses its
`fetch_json`. Pipeline: `collect_profiles` → `score_expertise` for every
non-None pair → `save_experts`. Prints `saved <n> of <m> -> <db>` to stdout
and `failed: <login>` per failure to stderr. Exit code 0 when all saved,
1 when any login failed, argparse's 2 on bad usage.

### 2.4. What must not break

All 40 v1 tests stay green unchanged; no v1 file under `megatron/` or
`tests/` is modified (every v2 target is a new file). Fixtures are read-only.
`collect_profiles`' signature and its fetcher contract stay as they are — the
client plugs in as `fetch_json=client.fetch_json`.

## 3. Acceptance

Test baseline at task time: **40**. Runner `venv/bin/python -m pytest`.
Value comparisons → `--tb=short` and `maxDiff = None` in every test class.
Stepped, narrow first:

```bash
# 0. syntax (every card, its targets)
venv/bin/python -c "import ast,sys; [ast.parse(open(f).read(), f, feature_version=(3,9)) for f in sys.argv[1:]]" <targets>

# A. client
venv/bin/python -m pytest tests/test_github_client.py -q --tb=short
# B. cli
venv/bin/python -m pytest tests/test_cli.py -q --tb=short
venv/bin/python -m megatron harvest --help > /dev/null
# C. order (blind spot): own test green on real code, RED on two mutants
venv/bin/python -m pytest tests/test_collect_order.py -q --tb=short
R=$PWD; for m in \
 's/return list(await asyncio.gather(\*tasks))/return [await f for f in asyncio.as_completed(tasks)]/' \
 's/return list(await asyncio.gather(\*tasks))/return list(reversed(await asyncio.gather(*tasks)))/'; do
  T=$(mktemp -d); cp -r megatron tests $T/; sed -i "$m" $T/megatron/collectors.py
  cmp -s megatron/collectors.py $T/megatron/collectors.py && { echo "MUTANT NOT APPLIED: $m"; exit 1; }
  (cd $T && $R/venv/bin/python -m pytest tests/test_collect_order.py -q --tb=no -p no:cacheprovider) && { echo "MUTANT SURVIVED: $m"; exit 1; }
done
# D. end to end, client + cli, offline
venv/bin/python -m pytest tests/test_harvest_e2e.py -q --tb=short

# regression: full run
venv/bin/python -m pytest tests -q --tb=short
# guard No Network In Core (revised): network only in github_client.py, and only urllib
bad=$(grep -lE "(import|from) +(urllib|requests|socket|http)" megatron/*.py | grep -vx megatron/github_client.py); test -z "$bad" || { echo "GUARD FAILED: network import in $bad"; exit 1; }
! grep -nE "(import|from) +(requests|aiohttp|httpx|socket|http)" megatron/github_client.py
grep -qE "(import|from) +urllib" megatron/github_client.py        # A and D only
! grep -n "urlopen" tests/*.py || { echo "GUARD FAILED: a test calls urlopen"; exit 1; }
```

Examples each test must prove (numbers from the fixtures):

**A. `GitHubClient`** — fake transport keyed by URL, serving fixture bodies
(`bytes`) and headers parsed from the `.headers.txt` files.
1. `parse_next_link` of page 1's `link` → `https://api.github.com/user/1024025/repos?per_page=5&page=2`; of page 2's → `...&page=3`; of page 3's, `None`, `""` → `None`.
2. `fetch_json("/users/torvalds/repos?per_page=5")` with page 1 served at `https://api.github.com/users/torvalds/repos?per_page=5` and pages 2, 3 at their `link` URLs → a list of 12 items; the transport saw exactly those 3 URLs in that order; `parse_repo_stats("torvalds", result)` → `repo_count` 12, `non_fork_count` 9, `total_stars` 262425.
3. `fetch_json("/users/torvalds")` served `user_torvalds.json` + `rate_limit_headers.txt` → dict with `login` "torvalds"; one transport call; `client.rate_limit == {"limit": 60, "remaining": 59, "reset": 1790594886}`.
4. `GitHubClient(token="t0k")` → transport saw `Authorization: Bearer t0k`; with `token=None` and `GITHUB_TOKEN=envtok` patched into `os.environ` → `Bearer envtok`; with neither → no `Authorization` key; `Accept` and `User-Agent` always present.
5. Headers of `rate_limit_headers.txt` with `x-ratelimit-remaining` set to "0", clock fixed at 1790594766, a recording async fake sleep: the first `fetch_json("/users/torvalds")` does not sleep; the second one sleeps exactly once, 120 seconds, before its request.
6. Status 404 with body `b'{"message": "Not Found"}'` → `GitHubError` raised, `.status == 404`.
7. `max_pages=2` on the 3-page chain → 10 items, 2 transport calls.
8. `GitHubClient()` with nothing patched has `transport is urllib_transport` (no call made).

**B. `harvest` / `main`** — async fake `fetch_json` over fixtures; "minnow"
is a copy of `user_torvalds.json` with `login` "minnow", `followers` 7, repos `[]`.
1. `harvest(["torvalds", "minnow"], fake, db)` → `{"requested": 2, "saved": 2, "failed": []}`; `top_experts(db, 2)` logins `["torvalds", "minnow"]`, scores `[850302, 7]`.
2. Fake raising `ValueError` for "minnow" → `{"requested": 2, "saved": 1, "failed": ["minnow"]}`; the table has 1 row.
3. `main(["harvest", "torvalds", "minnow", "--db", db], fetch_json=fake)` → 0, stdout has `saved 2 of 2`; with the failing fake → 1, stdout `saved 1 of 2`, stderr `failed: minnow`.
4. `subprocess.run([sys.executable, "-m", "megatron", "harvest", "--help"])` → returncode 0.

**C. Collect order** — 5 search logins; for `/users/<login>` the fake returns
a copy of `user_torvalds.json` with `login` = that login and `followers` =
its index 0..4, repos = `repos_torvalds.json`; it awaits
`asyncio.sleep(0.01 * (5 - index))` first, so later logins finish **earlier**.
1. `collect_profiles(logins, fake, concurrency=5)` → profile logins equal `logins`, followers `[0, 1, 2, 3, 4]`, stats logins equal `logins`.
2. Same with `concurrency=2` → same three lists.

**D. End to end** — real `GitHubClient` over a fake transport; no network.
1. Fake transport: `https://api.github.com/users/torvalds` → `user_torvalds.json` + `rate_limit_headers.txt`; `https://api.github.com/users/torvalds/repos?per_page=100` → page 1 body + page 1 headers; pages 2, 3 at their `link` URLs. `main(["harvest", "torvalds", "--db", db], fetch_json=GitHubClient(token="x", transport=fake).fetch_json)` → 0; `top_experts(db, 1)[0]` has `total_stars` 262425 and `expertise_score` 850316 (a single page would give 7836 / 341138); the transport was called 4 times.
2. `main(["harvest", "torvalds", "--db", db])` with **no** `fetch_json`, `megatron.github_client.urllib_transport` patched to the same fake and `GITHUB_TOKEN=envtok` in `os.environ` → 0, every call carried `Authorization: Bearer envtok`.

## 4. Constraints

1. Every target is a **new file** — no v1 file is edited; the edit envelope
   rule does not come into play.
2. Python 3.9-compatible syntax, stdlib only (`urllib.request`, `asyncio`,
   `json`, `argparse`, `unittest`, `unittest.mock`).
3. Code and its test — one card via `targets`. Criterion author ≠ code
   author: the order test and the end-to-end test are written by cards that
   do not write the code they test.
4. One file — one owner card; a card does not read a neighbour's target of
   the same generation. The fixtures above are committed before the run.
5. No test opens a socket: the transport and `fetch_json` are always faked,
   `urllib_transport` is only patched or identity-checked, never called.

## 5. Techniques that have already worked

- Domain fixture = verbatim API response (v1: 10/10 cards at attempt 1).
  The paginated fixtures were fetched the same way, 2026-09-28, unauthenticated.
- `--tb=short` + `maxDiff = None` for value comparisons.
- Card idiom copied from `.morph/runs/20260928-120143-5117d5a3/deck.json`
  (forensic snapshot, `set -e` subshell, AST 3.9 link).
- **New:** a test for a property is accepted only when it is **red on a
  mutant** that breaks that property — the acceptance runs the mutant itself.

## 6. What is intentionally NOT specified

Card breakdown, slices, order, per-card acceptance wording.

## 7. Out of scope

- Any real network call in tests or acceptance; `urllib_transport` itself is
  not exercised (operator smoke: `GITHUB_TOKEN=… venv/bin/python -m megatron harvest torvalds`, manual, optional).
- Retries, backoff on 5xx, secondary rate limits, `Retry-After`, 403 retry —
  a 403 with `remaining 0` raises `GitHubError`; the next request waits.
- Token pools/rotation, GitHub App auth, GraphQL.
- Pagination of anything but list responses via `Link: rel="next"`; the
  per-page size stays `per_page=100` in `collect_profiles`.
- Search crawling/user discovery (logins come from the command line only).
- 500K scale, distributed runs, resumable harvest, progress output.
- Editing any v1 file, including `collectors.py` and v1 tests; README, packaging.

## 8. How to run

```bash
cd ../MorphProject/mrph && set -a; source ../morph-lab/.env; set +a
venv/bin/mrph deck check --root ../../Megatron
venv/bin/mrph run --root ../../Megatron --processor glm --max-regenerations 12
```

Ceiling **$5**: `mrph run` has no dollar flag; at v1's $0.0012 per card, the
regeneration cap bounds the bill orders of magnitude below it.

## 9. Pre-registration of predictions

| quantity | prediction |
|---|---|
| cards | 4 |
| generations | 2 |
| provider bill | < $0.05 |
| cards with regeneration | ≤ 1 |
| mutants surviving the order test | 0 of 2 |
| tests at the end | ≥ 40 + 18 = 58 |

**Falsifiable claim:** all 4 cards are `written` within ≤ 2 attempts each,
and the order test is red on both mutants on the first accepted attempt.

## 10. What to record at the end

Cards written/failed/skipped, attempts per card, wall time per generation,
provider bill, final test count, `git log --oneline` of the run branch.

## 11. Actual

`<after the run>`
