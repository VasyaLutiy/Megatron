# TASK: PaukMegatron v4 — discovery: `search/users` pages → logins → `harvest`

Spec per `TASK_TEMPLATE.md` (mrph). Record: `contour.yaml` (group `search`,
function Discover Logins; Harvest example for `discover`). Previous specs and
their actuals: `docs/TASK_MEGATRON.md`, `_V2.md`, `_V3.md`.
Executor: Morph, processor `glm` (z-ai/glm-5.3-flash, route sync).

## 1. Why this

v3 (60 tests, merged) can harvest any login it is given, but **cannot find a
single login by itself**: every login so far was typed by hand. The v2 smoke
(`smoke-v2.log`, `saved 5 of 5 -> experts.db`) fed the 5 logins of
`search_users_python.json`, a v1 fixture captured by hand.

Measured 2026-09-28 12:46 GMT, anonymous `GET /search/users?q=followers:>5000&per_page=30`
(fixtures below):

- **1230** users match (`total_count`), `incomplete_results` false; the
  `link` header's `rel="last"` is **page 34** — 34 requests to walk the
  query at `per_page=30`, and 5 was the whole v2 smoke.
- Pages are disjoint and ordered: page 1 starts `torvalds, karpathy, claude`,
  page 2 starts `mattpocock, Microsoft-corp, getify`; 0 logins shared among
  the 60. Order is the API's, and nothing today preserves or even sees it.
- Search has **its own rate-limit resource**: every search response carries
  `x-ratelimit-resource: search`, `x-ratelimit-limit: 10` (anonymous, per
  minute; `reset` 1790599635 = 60 s after the first request at 1790599575),
  `remaining` 9 → 8 → 7 over the three captures. The repos pages of v2 carry
  `x-ratelimit-resource: core`, limit 60 (per hour). A 34-page walk therefore
  crosses at least 3 search windows anonymously.

The number this deck is judged by: `python -m megatron discover
"followers:>5000" --pages 2` over the real fixtures prints exactly the **60**
logins of pages 1 and 2 **in API order**, one per line — and a sorted or
per-page-reversed result makes a test red.

## 2. Contract

### 2.1. INPUT shapes with addresses

| shape | defined at |
|---|---|
| **Search response, page 1** | `tests/fixtures/search_page1.json` — verbatim body of `https://api.github.com/search/users?q=followers:%3E5000&per_page=30&page=1`, 2026-09-28 12:46:15 GMT, unauthenticated: `total_count` 1230, `incomplete_results` false, 30 `items`; logins `items[0..2]` = torvalds, karpathy, claude; `items[29]` = geohot |
| **Search response, page 2** | `tests/fixtures/search_page2.json` — fetched at page 1's `rel="next"` URL verbatim: `total_count` 1230, `incomplete_results` false, 30 items; `items[0..2]` = mattpocock, Microsoft-corp, getify; `items[29]` = pewdiepie-archdaemon |
| **Search response, empty** | `tests/fixtures/search_empty.json` — `https://api.github.com/search/users?q=followers%3A%3E100000000&per_page=30`: `{"total_count":0,"incomplete_results":false,"items":[]}` |
| **Their headers** | `tests/fixtures/search_{page1,page2,empty}.headers.txt` — verbatim (CR stripped), parsed as in v2: skip the first line (`HTTP/2 200`), strip, skip empty lines, split at the first `": "`. |
| `link` of page 1 | `<https://api.github.com/search/users?q=followers%3A%3E5000&per_page=30&page=2>; rel="next", <…&page=34>; rel="last"` |
| `link` of page 2 | four entries: `rel="prev"` (page 1), `rel="next"` → `https://api.github.com/search/users?q=followers%3A%3E5000&per_page=30&page=3`, `rel="last"` (34), `rel="first"` (1) — `next` is **not** the first entry |
| `link` of empty | absent |
| search rate-limit headers | page 1: `x-ratelimit-limit` 10, `-remaining` 9, `-used` 1, `-resource` search, `-reset` 1790599635; page 2: remaining 8; empty: remaining 7; `date` of page 1 = 1790599575 |
| v1 search response (5 logins) | `tests/fixtures/search_users_python.json`: `total_count` 1746, logins karpathy, openai, google, huggingface, rafaballerini |
| `API_ROOT`, `parse_next_link`, `GitHubError`, `GitHubClient` | `megatron/github_client.py:19`, `:22`, `:61`, `:70`; `fetch_json` `:99` — a **dict** body is returned as is after one request (`:125-126`), the `Link` of a dict response is not followed and not exposed |
| `client.transport` attribute (public, v2 §2.3), looked up at construction `:82` | Transport contract `(url, headers) -> (status, headers, body)`: `docs/TASK_MEGATRON_V2.md` §2.1 |
| rate-limit wait before every request | `megatron/github_client.py:111-113` (`seconds_to_wait(self.rate_limit, int(self.clock()))`); state replaced after every response `:117-119` — one state per client, whatever the resource |
| fake transport idiom | `tests/test_github_client.py:52` (`fake_transport(routes)`) |
| `main(argv=None, fetch_json=None)`, harvest subparser | `megatron/cli.py:39-61`; the deferred `GitHubClient` import `:50-53` |

The page-1 fixture was captured at `…q=followers:%3E5000&per_page=30&page=1`;
tests serve it at `search_url("followers:>5000")` (§2.3), exactly as v2 served
`repos_torvalds_page1` at the URL without `&page=1`. Page 2 is served at the
`rel="next"` URL of page 1, verbatim.

Domain data in tests is a **copy of a fixture** with at most named fields
substituted (`incomplete_results`, `x-ratelimit-remaining`, the `link`
header removed). Numbers are never invented.

### 2.2. OUTPUT shapes

- `parse_search_page(data)` → `{"logins": [str, ...], "total_count": int, "incomplete_results": bool}`,
  `logins` = `items[*].login` in item order.
- `discover_logins(...)` → `{"logins": [str, ...], "total_count": int, "incomplete_results": bool, "pages": int}`:
  `logins` concatenated in page order, duplicates kept; `total_count` from
  the first page; `incomplete_results` true if any page's is; `pages` = pages fetched.
- `discover` CLI: stdout = the logins, one per line, nothing else; stderr =
  `discovered <n> of <total_count>, pages <pages>`, plus
  `warning: incomplete_results` when true. Exit 0.

### 2.3. Names

| file | public names |
|---|---|
| `megatron/search.py` (new) | `encode_query(query) -> str`, `search_url(query, per_page=30) -> str`, `parse_search_page(data) -> dict`, `async discover_logins(client, query, pages, per_page=30) -> dict` |
| `megatron/cli.py` (patch) | subcommand `discover <query> [--pages N]` in `main`; `harvest` unchanged |
| tests | `tests/test_search.py` (P, Q, D), `tests/test_cli_discover.py` (C), `tests/test_discover_examples.py` (O, L, R) |

Behaviour:

- `encode_query`: UTF-8 bytes; `A-Z a-z 0-9 - . _ ~` kept, every other byte
  `%XX` (upper-case hex). This is GitHub's own form in the `link` header:
  `followers:>5000` → `followers%3A%3E5000`.
- `search_url(q, n)` = `API_ROOT + "/search/users?q=" + encode_query(q) + "&per_page=" + str(n)`.
- `discover_logins(client, query, pages, per_page=30)`, `client` a `GitHubClient`:
  - `pages < 1` → `ValueError`, no request.
  - Every page is fetched with `await client.fetch_json(url)` — so the
    client's rate-limit wait, `GitHubError` and headers apply to every page.
    The first URL is `search_url(query, per_page)`; each next URL is the
    `rel="next"` of the previous page's `link` header (case-insensitive name),
    **verbatim**, via `github_client.parse_next_link`. No URL is built from a
    page number.
  - To see that header, `discover_logins` replaces `client.transport` for the
    duration of the call with a wrapper that calls the original transport,
    remembers the last response's `link`, and returns the triple unchanged;
    the original is restored in `finally` (also when `GitHubError` propagates).
  - Each page body goes through `parse_search_page`, looked up as a **module
    global at call time** (a later redefinition in the module takes effect).
  - Stops after `pages` pages or when a page has no `rel="next"`.
- CLI: `python -m megatron discover "<query>" [--pages N]` (`--pages` int,
  default 1). `main` builds `GitHubClient()` (deferred import, as for
  `harvest`; `fetch_json` is ignored by `discover`), runs `discover_logins`
  with `asyncio.run`, prints per §2.2, returns 0. `search` is imported inside
  the `discover` branch. `GitHubError` is not caught (non-zero exit).
- Composition: `python -m megatron discover "followers:>5000" --pages 2 | xargs python -m megatron harvest`.

### 2.4. What must not break

All 60 existing tests green and unmodified. Byte for byte: every file under
`megatron/` except `cli.py`, every existing test, every fixture. `cli.py`
edit envelope: ≤ 60 lines added, ≤ 5 deleted; `harvest` behaves as in v2.
Guard No Network In Core unchanged: network imports only in
`github_client.py`, and only urllib — `search.py` imports no `urllib`
(hence the hand-written `encode_query`).

## 3. Acceptance

Test baseline at task time: **60** (`60 passed`, measured 2026-09-28 on
master `7f9b216`). Runner `venv/bin/python -m pytest`. Value comparisons →
`--tb=short`, `maxDiff = None`, whole-list / whole-dict equality. Stepped,
narrow first. Mutants are applied to a temp copy of `megatron/` and `tests/`;
a mutant that did not apply, or that a named test survives, fails the step.

```bash
# 0. syntax, every target
venv/bin/python -c "import ast,sys; [ast.parse(open(f).read(), f, feature_version=(3,9)) for f in sys.argv[1:]]" <targets>

# mutation helper: $1 file, $2 "append:<file>" or sed script, $3 test file
R=$PWD; mut() { T=$(mktemp -d); cp -r megatron tests $T/
  case "$2" in append:*) cat "${2#append:}" >> $T/$1;; *) sed -i "$2" $T/$1;; esac
  cmp -s $1 $T/$1 && { echo "MUTANT NOT APPLIED: $2"; exit 1; }
  (cd $T && $R/venv/bin/python -m pytest $3 -q --tb=no -p no:cacheprovider) && { echo "MUTANT SURVIVED: $2"; exit 1; }
  echo "mutant killed: $2"; }
# M1 (per-page reversed), appended to megatron/search.py:
#   _m_parse = parse_search_page
#   def parse_search_page(data):
#       page = _m_parse(data); page["logins"] = list(reversed(page["logins"])); return page
# M2 (sorted), appended to megatron/search.py:
#   _m_discover = discover_logins
#   async def discover_logins(client, query, pages, per_page=30):
#       result = await _m_discover(client, query, pages, per_page)
#       result["logins"] = sorted(result["logins"]); return result
# M3 (no rate-limit wait): sed 's/await self.sleep(wait)/pass/' on megatron/github_client.py

# P/Q/D. search module
venv/bin/python -m pytest tests/test_search.py -q --tb=short
mut megatron/search.py append:M1 tests/test_search.py
# C. CLI
venv/bin/python -m pytest tests/test_cli_discover.py tests/test_cli.py -q --tb=short
venv/bin/python -m megatron discover --help > /dev/null
venv/bin/python -m megatron harvest --help > /dev/null
mut megatron/search.py append:M2 tests/test_cli_discover.py
set -- $(git diff --numstat HEAD -- megatron/cli.py); [ "${1:-0}" -ge 1 ] && [ "$1" -le 60 ] && [ "$2" -le 5 ] || { echo "ENVELOPE FAILED: cli.py +${1:-0}/-${2:-0}"; exit 1; }
# O/L/R. judge: order, Link, search rate limit
venv/bin/python -m pytest tests/test_discover_examples.py -q --tb=short
mut megatron/search.py append:M1 tests/test_discover_examples.py
mut megatron/search.py append:M2 tests/test_discover_examples.py
mut megatron/github_client.py 's/await self.sleep(wait)/pass/' tests/test_discover_examples.py

# regression: full run, then guards
venv/bin/python -m pytest tests -q --tb=short
git diff --quiet HEAD -- megatron/__init__.py megatron/__main__.py megatron/api_manager.py megatron/collectors.py megatron/github_client.py megatron/parsers.py megatron/processors.py megatron/storage.py tests || { echo "GUARD FAILED: an existing file modified"; exit 1; }
bad=$(grep -lE "(import|from) +(urllib|requests|socket|http)" megatron/*.py | grep -vx megatron/github_client.py || true); test -z "$bad" || { echo "GUARD FAILED: network import in $bad"; exit 1; }
! grep -nE "(import|from) +(requests|aiohttp|httpx|socket|http)" megatron/github_client.py
! grep -n "urlopen" tests/*.py || { echo "GUARD FAILED: a test calls urlopen"; exit 1; }
```

Fakes: a **fake transport** keyed by URL (v2 idiom) returning
`(200, <parsed .headers.txt>, <fixture bytes>)`, recording every URL; an
unknown URL answers `(404, {}, b'{"message": "Not Found"}')`. Clients are
real `GitHubClient(token="x", transport=fake, ...)`. `Q` below =
`"followers:>5000"`, `U1 = search_url(Q)` =
`https://api.github.com/search/users?q=followers%3A%3E5000&per_page=30`,
`U2` = page 1's `rel="next"` =
`https://api.github.com/search/users?q=followers%3A%3E5000&per_page=30&page=2`.
`L1`, `L2` = the 30 logins of page 1, page 2 read from the fixtures.

**P. `parse_search_page`**
1. page 1 → `{"logins": L1, "total_count": 1230, "incomplete_results": False}`; `L1[:3] == ["torvalds", "karpathy", "claude"]`, `L1[29] == "geohot"`.
2. page 2 → logins `L2`, `L2[:3] == ["mattpocock", "Microsoft-corp", "getify"]`, `L2[29] == "pewdiepie-archdaemon"`, total 1230.
3. empty → `{"logins": [], "total_count": 0, "incomplete_results": False}`.
4. `search_users_python.json` → logins karpathy, openai, google, huggingface, rafaballerini, total 1746; a copy of page 1 with `incomplete_results` true → `True`.

**Q. URL**
1. `encode_query("followers:>5000") == "followers%3A%3E5000"`; `search_url("followers:>5000") == U1`; `search_url("followers:>5000", 30) + "&page=2" == U2`.
2. `encode_query("language:python followers:>5000") == "language%3Apython%20followers%3A%3E5000"`; `encode_query("a-b_c.d~e") == "a-b_c.d~e"`.

**D. `discover_logins`** — routes U1 → page 1 (+headers), U2 → page 2 (+headers).
1. `pages=2` → `{"logins": L1 + L2, "total_count": 1230, "incomplete_results": False, "pages": 2}`; 60 logins; transport URLs `[U1, U2]`.
2. `pages=1` → logins `L1`, `pages` 1, transport URLs `[U1]`.
3. Query `"followers:>100000000"` routed to `search_empty` (+headers), `pages=3` → `{"logins": [], "total_count": 0, "incomplete_results": False, "pages": 1}`, one transport call.
4. Page 1 headers with `x-ratelimit-remaining` "0", `clock=lambda: 1790599575`, a recording async fake sleep; `pages=2` → sleeps exactly once, `[60]`, recorded between the two transport calls; afterwards `client.rate_limit == {"limit": 10, "remaining": 8, "reset": 1790599635}`.
5. After D.1 `client.transport is fake`; with U2 unrouted (404), `pages=2` raises `GitHubError` with `.status == 404` and afterwards `client.transport is fake`.
6. `pages=0` → `ValueError`, zero transport calls.

**C. CLI** — `megatron.github_client.urllib_transport` patched to the fake
(v2 D.2 idiom), stdout/stderr captured.
1. `main(["discover", "followers:>5000", "--pages", "2"])` → 0; stdout lines `== L1 + L2` (60, in order); stderr contains `discovered 60 of 1230, pages 2`.
2. `--pages` omitted → stdout lines `== L1`, one transport call; stderr `discovered 30 of 1230, pages 1`.
3. Empty query (`"followers:>100000000"`) → 0, stdout empty, stderr `discovered 0 of 0, pages 1`.
4. Page 1 copy with `incomplete_results` true → stderr contains `warning: incomplete_results`; stdout unchanged (`L1`).
5. `subprocess.run([sys.executable, "-m", "megatron", "discover", "--help"])` → 0; `main(["harvest", "--help"])` still exits 0 (`SystemExit`).

**O/L/R. Judge** — written by a card that does not write `search.py`; calls `search.discover_logins` via the module at call time.
- O.1 (order) = D.1 as whole-list equality `L1 + L2`, plus `result["logins"][29:31] == ["geohot", "mattpocock"]` (the page seam). Red on M1 and M2.
- L.1 (Link is the only pager) — page 1 headers with the `link` entry **removed**, U2 still routed to page 2; `pages=2` → logins `L1`, `pages` 1, transport URLs `[U1]`.
- R.1 (search rate limit through the client) = D.4. Red on M3.

## 4. Constraints

1. New files: `megatron/search.py` and the three tests. One existing file is
   edited, `megatron/cli.py`, wiring only, envelope ≤ 60 added / ≤ 5 deleted.
2. Python 3.9-compatible syntax, stdlib only; `search.py` imports no network
   library (no `urllib.parse` either — the guard greps `urllib`).
3. Code and its test — one card via `targets`. The judge (O/L/R) does not
   write the code it tests.
4. One file — one owner card; a card does not read a neighbour's target of
   the same generation. Fixtures are committed before the run.
5. No test opens a socket; the transport is always faked; `urllib_transport`
   is only patched. No real sleep beyond 0.01 s.

## 5. Techniques that have already worked

- Verbatim fixtures fetched the same way as v2's pages (v1–v3: 17/17 cards
  written, 1 regeneration).
- Mutation-gated acceptance (v2: 0/2 survivors, v3: 0/5).
- **New:** mutants by **appending** a redefinition to the new module instead
  of `sed` on code nobody has seen yet — it needs only the §2.3 names and the
  "module global at call time" rule.
- Card idiom from `.morph/runs/20260928-131231-529b11aa/deck.json`.

## 6. What is intentionally NOT specified

Card breakdown, slices, per-card acceptance wording; the wrapper's name and
shape inside `search.py`; how `cli.py` lays out the new branch.

## 7. Out of scope

- **Retry / backoff / `Retry-After` / 403 and 429 handling — including the
  search secondary rate limit.** No measured refusal exists: the three
  captures of 2026-09-28 12:46 are all `HTTP/2 200` (search `remaining`
  9, 8, 7 of 10), `smoke-v2.log` is `saved 5 of 5`, `smoke-v2-big.log` is
  absent. No refusal body or header to fixture — no section. Behaviour stays
  as v2/v3 §7: status ≥ 400 raises `GitHubError`; the next request waits on
  the client's rate-limit state.
- Separate rate-limit state per resource (`core` vs `search`): the client
  keeps one state, the last response's. In the `discover | xargs harvest`
  composition each command is its own process with its own client, so the
  two never share a state.
- The 1000-result search cap and query splitting to get past it
  (1230 matches, `rel="last"` page 34); `--per-page`, sort/order qualifiers,
  deduplication (duplicates are kept as the API returns them).
- Throughput of the composition: anonymously `harvest` gets 60 core
  requests/hour = 30 logins; not addressed.
- Catching `GitHubError` in `discover` (a traceback and non-zero exit are
  accepted).
- Any real network call in tests or acceptance; operator smoke
  (`venv/bin/python -m megatron discover "followers:>5000" --pages 2 | head`) is manual.
- Editing any existing file other than `megatron/cli.py`; README, packaging.

## 8. How to run

```bash
cd ../MorphProject/mrph && set -a; source ../morph-lab/.env; set +a
R=/home/john/Documents/Work2026/Megatron        # absolute: relative --root commits nothing (v3 §11)
venv/bin/mrph deck clear --root $R && venv/bin/mrph deck reset --root $R
venv/bin/mrph deck add --root $R --file $R/decks/v4.json
venv/bin/mrph deck check --root $R
venv/bin/mrph run --root $R --processor glm --route sync --max-regenerations 9
```

Ceiling **$5**: v2 cost $0.0110 for 5 requests, v3 $0.00286 for 3; 9
regenerations bound the bill two orders of magnitude below it.

## 9. Pre-registration of predictions

| quantity | prediction |
|---|---|
| cards | 3 |
| generations | 2 |
| provider bill | < $0.03 |
| cards with regeneration | ≤ 1 |
| mutants surviving | 0 of 5 (M1×2, M2×2, M3) |
| `cli.py` envelope | ≤ +60 / −5 |
| tests at the end | 60 + 12 (P4 Q2 D6) + 5 (C) + 3 (O L R) = 80 |

**Falsifiable claim:** all 3 cards `written` within ≤ 2 attempts each, no
mutant survives, and the operator smoke prints 60 lines starting `torvalds`.

## 10. What to record at the end

Cards written/failed/skipped, attempts per card, wall time per generation,
provider bill, final test count, mutant kill table, `cli.py` numstat,
`git log --oneline` of the run branch.
