# TASK: PaukMegatron v1.0 — offline core of the GitHub Expert Data Harvester

Spec per `TASK_TEMPLATE.md` (mrph). Record: `contour.yaml` at the repo root.
Scenario C: the deck is executed by Claude Code agents, judge cards by a
separate fresh agent.

## 1. Why this

The target system must harvest and rank 500,000 GitHub expert profiles.
Today the repository has **0 lines of code and 0 tests** (baseline measured
2026-09-28). Before any scale work, the core contract must exist and be
provable offline: 3 real API calls on 2026-09-28 produced the fixtures in
`tests/fixtures/` (user 1358 B, repos 70693 B, search 5756 B, headers
7 lines), and every number in the acceptance layer is taken from them.
This deck is also the paradigm test: the orchestrator writes 0 lines of code.

## 2. Contract

### 2.1. INPUT shapes with addresses

Every shape a card's test must **construct or parse** is defined here:

| shape | defined at |
|---|---|
| GitHub user JSON | `tests/fixtures/user_torvalds.json` (verbatim API response) |
| GitHub repos JSON | `tests/fixtures/repos_torvalds.json` (12 items, 3 forks) |
| Search response | `tests/fixtures/search_users_python.json` (total_count 1746, 5 items) |
| Rate-limit headers | `tests/fixtures/rate_limit_headers.txt` (limit 60, remaining 59, reset 1790594886) |
| Rate Limit State, Expert Profile, Repo Stats, Expert Pair, Expert Record | `contour.yaml` → `dataObjects`, exact keys |

Domain fixtures are **copies of these files**, not compositions. Do not
invent field values; read them from the fixture.

### 2.2. OUTPUT shapes

Exact keys in `contour.yaml` `dataObjects`. `Expert Record` is the Expert
Profile dict **extended** with `total_stars, languages, expertise_score,
primary_language` — no second serialization of the profile. `top_experts`
returns Expert Records with `languages` decoded to a dict.

### 2.3. Names

| module | public names |
|---|---|
| `megatron/api_manager.py` | `parse_rate_limit(headers)`, `seconds_to_wait(state, now)` |
| `megatron/parsers.py` | `parse_user_profile(data)`, `parse_repo_stats(login, repos)` |
| `megatron/collectors.py` | `async collect_profiles(logins, fetch_json, concurrency=10)` |
| `megatron/processors.py` | `score_expertise(profile, stats)` |
| `megatron/storage.py` | `save_experts(db_path, records)`, `top_experts(db_path, n=10)` |
| tests | `tests/test_api_manager.py`, `tests/test_parsers.py`, `tests/test_collectors.py`, `tests/test_processors.py`, `tests/test_storage.py` |

DB table: `experts`, key `login`. Score formula, fixed:
`expertise_score = followers + 2 * total_stars`; torvalds fixture →
`325466 + 2*262418 = 850302`.

### 2.4. What must not break

Nothing exists yet; what must hold: fixtures under `tests/fixtures/` are
**read-only** (no card rewrites them), `megatron/__init__.py` stays, and the
final tree passes the full suite plus the network-import guard below.

## 3. Acceptance

Test baseline at task time: **0**. Runner: `venv/bin/python -m pytest`.
Per area, stepped, narrow first (values are compared here, so `--tb=short`
and `maxDiff = None` in every test class):

```bash
# per card, from repo root
venv/bin/python -c "import ast,sys; [ast.parse(open(f).read(), f, feature_version=(3,9)) for f in sys.argv[1:]]" <targets>
venv/bin/python -m pytest tests/test_<module>.py -q --tb=short
venv/bin/python -m pytest -q --tb=short          # full run, regression guard
# guard: no network in core (all cards)
n=$(grep -lE "import (urllib|requests|socket|http)" megatron/*.py | wc -l); test "$n" -eq 0
```

Tests are unittest style, `msg=` on every assertion, one test per numbered
example, offline only (Requirement `Offline Tests`).

## 4. Constraints

1. All targets are **new files** — the additive rule is absolute; the only
   pre-existing files are fixtures (read-only) and `megatron/__init__.py`.
2. Python 3.9-compatible syntax, stdlib only (Requirement `Stdlib Only`).
3. Code and its test — one card via `targets`; judge tests are separate
   `-judge` cards by a fresh agent.
4. One file — one owner card. A card does not read a neighbour's target in
   the same generation.
5. `collect_profiles` takes the fetcher as an argument; no module under
   `megatron/` imports a network library (Guardrail `No Network In Core`).

## 5. Techniques that have already worked

- Domain fixture = copy of a real artifact: all four fixtures are verbatim
  API responses fetched 2026-09-28; tests load them with `json.load`.
- Value-comparison failures need verbose diffs: `--tb=short` +
  `maxDiff = None` (TASK_TEMPLATE measurement 20.09).

## 6. What is intentionally NOT specified

The card breakdown, slices, order, acceptance wording per card, generation
count. That is the planner/orchestrator's output, not the spec's.

## 7. What is out of scope for this deck

- Real network collection, the live GitHub client (urllib/aiohttp wrapper).
- Token pools, token rotation, authentication of any kind.
- User discovery/search crawling (the search fixture is used only as a
  source of 5 logins for the collector test).
- The 500,000-profile scale run, distributed scanning, queues, sharding.
- CLI, web UI, reporting, GraphQL API, pagination beyond one repos page.
- README and packaging.

## 8. How to run

Scenario C (`SIMPLE_RUNBOOK.md` шаг 4C–6C): deck cut by
`mrph plan --spec contour.yaml --root ../Megatron --judge`, checked by
`deck check`, saved to `decks/v1.json`, executed by two Claude Code agents
(model sonnet): executor → code cards, fresh judge → `-judge` cards. Branch
`morph/v1`, merge is the operator's act.

## 9. Pre-registration of predictions

| quantity | prediction |
|---|---|
| cards in the deck | 10 (5 code + 5 judge) |
| generations | 3 (parsers → collectors; judges after code) |
| executor bill | $0 beyond subscription |
| cards with >1 acceptance run | ≤ 2 |
| judge defects found in code | ≤ 1 |
| tests at the end | ≥ 20 |

**Falsifiable claim:** all 5 code cards reach `exit 0` in ≤ 3 acceptance
runs each, and the judge's tests fail on at most 1 code card.

## 10. What to record at the end

Cards accepted/burned, acceptance runs per card, defects found by the judge
(example number), wall time per agent, final test count,
`git log --oneline` of the branch, ccledger API-equivalent of both agent
sessions.

## 11. Actual

*(to be filled after the run)*
