---
name: morph-agent-run
description: Execute a Morph deck with Claude Code agents, with no external model and no OpenRouter key — one agent on claude-sonnet-5 writes the code cards, another, fresh one the judge cards (`--judge`); the card's acceptance stays the judge, one commit per card with Morph-Card trailers so primer sees ownership. Use when asked to "run the deck with an agent", "run the cards without Morph", "do it as Scenario C", "without glm", "run the deck on sonnet", or when there is no OpenRouter key and the deck is already cut.
---

# A Morph deck executed by Claude Code agents

You are the orchestrator of Scenario C from `documentation/SIMPLE_RUNBOOK.md`. **You do not
write code.** The deck already exists or is cut by the planner; you launch two
agents, read their reports and talk to the operator in numbers. Everything not
described here comes from the craft of cards: `documentation/Morph_SKILL.md`.

Why this way and not with Morph: the 27.09 measurement on one and the same deck of three cards —
Morph on glm-5.3 took 24 minutes, $0.51 and left a blocking defect; the Claude Code agent took
8 minutes, zero dollars beyond the subscription, 13 of 14 spec rules to the letter. When there are
few cards, the files are large or iteration is needed — the agent. When there are many cards and
they are alike, and an archive with numbers is needed — Morph (`morph-orchestrator`).

## What must exist before the start

- The project repository with a clean tree and its own branch for the work.
- The deck as a file `decks/<name>.json` in the flat card form (`custom_id, intent,
  targets, context_slice, acceptance, instruction, depends_on?`). Where from:
  `venv/bin/mrph plan --spec contour.yaml --root <project> --judge` from the mrph
  root (record → deck), or cut by the orchestrator by hand.
- The deck is checked: `deck add --file` → `deck check` → `deck clear`. Zero
  ownership and edge errors; Morph's backlog is not needed here.
- Every acceptance is run by hand on an empty tree and fails **only** on
  the absence of its own files. An acceptance that does not start burns attempts
  blind — for the agent just as for Morph.
- In acceptances that run the whole test suite: the fake processor environment is
  exported **before** the tests, the flaky `test_submit_stdout_parses_even_when_a_card_compiles`
  is excluded (`--deselect`). Both defects of 27.09 brought down both Morph and the agent.

## Order

1. **Briefs.** `python3 scripts/briefs.py <repository> <decks/name.json>`
   prints the generations, the list of code cards and judge cards and two ready briefs with
   paths. The brief texts are `references/executor-brief.md` and
   `references/judge-brief.md`; change only the paths, the branch and the model in them.
2. **Executor.** One `Agent` of type `general-purpose`, model `sonnet`,
   the executor brief in full. It goes through the code cards in `depends_on` order,
   runs each one's acceptance until `exit 0`, commits each separately with trailers.
   Do not launch a second executor in the same tree in parallel.
3. **Judge.** Only after the executor's report — a second `Agent`, **fresh**,
   model `sonnet`, the judge brief. It sees the spec, the examples and the finished code, but did not
   see how the code was written. The author of the criterion is not the author of the code: a rule that
   on 27.09 twice saved cards that had been burning six attempts each when one model wrote both the code and the test.
4. **Failure.** The agent did not reach `exit 0` in a reasonable number of runs — do not
   fix the code yourself. Three kinds of cause, as with Morph: the executor made a mistake
   (give it the diagnosis from `acc.log`, one retry); an example or a number in the spec
   is wrong (fix the spec/record, not the code); the record is silent (add an example).
   Determining the kind from `acc.log` is your job, not the agent's.
5. **Report to the operator in numbers:** cards accepted / burned, acceptance runs per
   card, what failed before green, `git log --oneline` of the branch, wall time,
   and the API equivalent of the agents' session via
   `venv/bin/python -m ccledger session <journal> --json` from
   the ccledger project (https://github.com/VasyaLutiy — a ledger of Claude Code sessions) (agent journals are at
   `~/.claude/projects/<slug>/<session-id>/subagents/*.jsonl`).
6. **Merge is a human act.** The branch stays local, the operator does the push
   and the merge.

## Trailers are not decoration

Agents have no `.morph/runs/` archive, which `mrph run` writes. The only
trace is the commits. So every accepted card is committed with

```
Morph-Card: <custom_id>
Morph-Model: claude-sonnet-5
Morph-Acceptance-Exit: 0
```

`mrph primer` reads `Morph-Card` from git and builds from them the file ownership map
for the next session ("git carries N Morph commits"). Without trailers the
next session starts from nothing. What primer does not get this way:
the edit envelope and "what burned cards" — only Morph runs have those.

## What not to do

- Do not give one agent both the code and the judge cards "since it is already in context".
- Do not read the project's code yourself to "help" the agent: that is what
  `mrph scout --seed-from-primer` for a cent or the agent itself is for.
- Do not adjust the acceptance to failing code. The code or the spec is what gets fixed.
- Do not push or merge the branch.
- Do not run the executor and the judge at the same time in one tree.
- Do not treat "all acceptances green" as proof of more than is written in the
  acceptances: the judge's blind spot passes through any executor (27.09:
  the defect "map after the acceptance is built" got past the judge for both builders).
