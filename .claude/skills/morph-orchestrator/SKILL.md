---
name: morph-orchestrator
description: The full Morph orchestrator cycle in one session — from goal to run. Code recon with a budget, a spec by TASK_TEMPLATE, cutting a deck of Morph cards, the run and a report in numbers. Use when asked to "build a deck", "cut a deck", "write a spec and a deck", "put Morph on" a specific task, epic, or pain from Head_Pains.
---

# Morph orchestrator: from goal to run

You are the orchestrator. **You do not write code — not a single line.** You produce two things:
a specification (the contract and the criteria) and a deck of Morph cards. The code is written by executors on
the batch API, and they are judged by the acceptance you formulate.

The craft of cards is in `documentation/Morph_SKILL.md`: eight rules, the card fields, how
to read a failure. The shape of the spec is in `documentation/TASK_TEMPLATE.md`. This skill is about
**the order of work**, not the craft; read it as a procedure, and those two as
references, where needed.

Previously one session wrote the spec and another, with a clean context, cut the deck. That
gave an independent check of the criteria, but cost a double warm-up: the second
session reread the same files. Here the roles are merged, and the lost check
is replaced by the **operator gate** in phase 3 — the operator looks at the acceptances only.

---

## Phase 1. Recon with a budget

The goal of this phase is not "to understand the project" but to assemble an **address map**: which contract
lives where, down to the line. This map later goes into §2.1 of the spec and becomes what
saves reading, both for you and for whoever comes next.

**Measure first, then read.** Numbers are cheaper than text, and the spec needs them:

```bash
git log --oneline -5 && git status --short
venv/bin/python -m pytest -q --tb=no 2>&1 | tail -1      # baseline
for f in <candidate-files>; do
  printf '%-28s %5s lines %4s """\n' "$f" \
    "$(wc -l < $f)" "$(python3 -c "print(open('$f').read().count(chr(34)*3))")"
done                                                      # prose guards
```

**Read places, not files.**

- `grep -n 'def <name>\|class <name>' <file>` → `sed -n '<A>,<B>p' <file>`.
- A file longer than ~600 lines is **never** read in full. In this project those are
  `cards/store.py`, `cards/generations.py`, `flows/morph.py`, `processors/batch.py`.
- If the session has codegraph — `codegraph_explore` instead of grep+read: it
  returns the source of the symbols you need, not the file.
- A file the deck does not touch is not read at all. `flows/morph.py` is needed
  only by decks about the REPL.

**Phase budget: about fifteen reads.** Past thirty, you are studying the
project instead of solving the task. Stop and start writing the spec: whatever
is missing, you will read later, by address.

**Product of the phase** — a table: contract → `file:line` → what is defined there.

## Phase 2. The spec

By `documentation/TASK_TEMPLATE.md`, all sections. What must not be spoiled:

- **§1 — motive in numbers.** Not "inconvenient" but "the card burned three attempts, two dependent
  ones went down in the cascade". No number — no section.
- **§2.1 — INPUT shapes with addresses.** Every shape the code must
  *construct*, and where it is defined. This rule was paid for with three burned
  attempts: you can call without reading, you cannot construct.
- **§2.3 — names.** Exact names of modules, functions, fields, flags, statuses.
  By them the next card finds what the previous one wrote.
- **§3 — acceptances, stepped.** From narrow to broad: its own test → tests of the touched
  modules → full run → prose guard. Regeneration receives the output of the **first**
  failing link, so the narrow goes first. `-q --tb=line` everywhere.
- **§4 — constraints**, including two from the project: a file a card writes does not
  lie in the context slices of its neighbours in the generation (otherwise `stale-context`); a fix does not
  affect the current run, because the modules are already in memory.
- **§7 — what is out of scope.** An explicit list, otherwise the deck will sprawl.

**There are no cards in the spec — not even now, when you will cut them yourself.** The spec is a
contract, not a plan: it is read months later to understand what was ordered, not
how it was executed. And a scope without a locally runnable acceptance does not go into the spec: a card
with a weak criterion is a wish.

**Commit** the spec before cutting. The deck is compiled from the tree; an uncommitted
spec leaves the tree dirty, and the run will not start.

## Phase 3. Operator gate

Show the human two sections: **§3 (acceptance commands)** and **§7 (out of scope)**.
Everything else can be fixed by regeneration; a mistake in a criterion costs three
burned attempts and a cascade of dependent cards, and "correct code with a red
acceptance" is always the fault of the criterion's author.

Wait for the answer. Do not start typing cards before that.

## Phase 4. The deck

Card boundaries are cut by **file ownership**, not by the logic of the task.

1. **Ownership map:** one file — one owner card per generation.
2. **Generations only by physical reading.** `depends_on` goes where a
   card reads what a neighbour writes, and nowhere else: every generation is a
   separate 20–45 minute wait in the queue.
3. **The context slice is explicit.** Everything a card must *construct* must have its definition
   in the context slice. Take a domain fixture as a copy of a real artifact from
   `.morph/runs/*/`, do not make one up.
4. **Code and its test — one card** via `targets`.
5. **An edit envelope of 20–60 lines on an existing file is a gate.** More — split
   the card, do not widen the context slice. Pure logic goes into a new file, into a large
   file — only wiring.
6. **A wide card goes with `variants: 2`** and a stepped acceptance.
7. **One model per deck.**

Before submitting:

```bash
venv/bin/mrph deck check        # file ownership and forgotten edges
```

and **run every acceptance by hand**. A command that does not start burns three
attempts blind.

## Phase 5. The run

```bash
venv/bin/mrph run --processor @<id>
```

The headless way: resilience to disconnects exists in `mrph run` and `mrph collect
--wait`, while the REPL command `/collect wait` can still be fragile in older
trees. The branch `morph/<deck-id>` stays local — push and merge are human.

While the run is going, **keep out of the tree**: the cards are already compiled, editing a file
by hand gives the neighbours `failed (stale-context)`, and the answer is thrown away unread.
Reading files is fine.

The diagnosis of a failed attempt disappears: `earlier_failures` is not serialized
(`Head_Pains` 2.15), and the rollback happens right after the acceptance fails. If you need to analyse
attempts, put the snapshot **into the acceptance in advance**, as the first command of the chain:

```sh
D=/tmp/morph/<card>; mkdir -p $D
cp <target> $D/attempt-$(date +%s).py
<rest of the chain> > $D/acc.log 2>&1; rc=$?; cat $D/acc.log; exit $rc
```

The report on completion — **in numbers**: accepted / failed / skipped, generations,
regenerations, minutes per batch, final test count, the provider's bill.

## Phase 6. Verification is not yours to do

You wrote both the criterion and the deck — you will confirm your own work. External verification
is run by a separate session following `documentation/VERIFY_RUNBOOK.md`: every deletion in the
diff is read by eye, card tests are checked by mutation (the same test against
`main` must fail), and an independent probe is written for every scope area of the spec.

Merging into `main` is a human act.

---

## What not to do

- Do not read a large file in full for the sake of one symbol.
- Do not put the breakdown into cards in the spec.
- Do not take into the deck a scope that has no locally runnable acceptance.
- Do not set `depends_on` "just in case": depth is paid for in queue time.
- Do not widen the context slice instead of splitting the card.
- Do not treat a green run as proof: an acceptance proves exactly what is
  written in it.
