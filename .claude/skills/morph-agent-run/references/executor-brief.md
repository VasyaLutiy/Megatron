# Card executor brief (Claude Code agent, model sonnet)

Substitute `<REPO>`, `<BRANCH>`, `<DECK>`; change nothing else. This is the brief
with which on 27.09 the agent executed the three `plan --spec` cards in 8 minutes, each
acceptance passing on the first run.

```
You are implementing work items ("cards") of a Morph deck in the Python project at <REPO>
(git branch <BRANCH>; work ONLY inside that directory; do not push; do not switch branches).

The file <DECK> is a JSON list of cards. Each card has: `targets` (the files you must create or
edit), `context_slice` (files to read first), `instruction` (exact requirements), `acceptance`
(a bash script that must exit 0), `depends_on` (order). Do the CODE cards only -- every card whose
custom_id does NOT end with `-judge` -- in dependency order.

For each card:
1. Read its context_slice files and its instruction in full. Follow the instruction literally:
   exact module names, function names, constants, file paths, test expectations. Do not invent
   names the instruction or the referenced docs do not give.
2. Write exactly the `targets` files (create new ones; edit existing ones only as the instruction
   allows).
3. Run the card's acceptance from the repository root with `bash -c '<acceptance>'` -- read it
   from the JSON with python, do not retype it. Iterate until it exits 0. The acceptance prints
   its own log; when it fails, read the log and fix the CODE, never the acceptance.
4. Commit the card's targets with `git -c commit.gpgsign=false commit` and this message:
     morph <custom_id>: <targets joined by ", ">

     Morph-Card: <custom_id>
     Morph-Model: claude-sonnet-5
     Morph-Acceptance-Exit: 0

Constraints: Python 3.9-compatible syntax (no `match`, no `X | Y` unions); standard library only
unless the instruction says otherwise; tests in unittest style with `msg=` on every assertion and a
docstring per test naming the example or rule it proves; module docstrings say what the module does
NOT do; comments explain why, not what. Never modify a file that is not in the current card's
targets. Never modify tests written by other cards.

When every code card is committed, report: for each card the number of acceptance runs and what
failed before it passed; the output of `git log --oneline <base>..HEAD`; anything in the
instructions you found ambiguous and how you resolved it.
```
