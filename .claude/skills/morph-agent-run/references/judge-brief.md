# Judge brief (a second, fresh Claude Code agent, model sonnet)

Launch only after the executor's report. Substitute `<REPO>`, `<BRANCH>`,
`<DECK>`. The judge did not see how the code was written, and must not: it checks what
the examples and the spec say, not what the code does.

```
You are the independent author of acceptance tests for a Morph deck in the Python project at <REPO>
(git branch <BRANCH>; work ONLY inside that directory; do not push). Somebody else has already
implemented the CODE cards of <DECK> and committed them. You implement the JUDGE cards only --
every card whose custom_id ends with `-judge` -- in dependency order.

You are the author of the criterion, not of the code. For each judge card:
1. Read its context_slice: the spec, the record and its examples, and the finished code it judges.
   Test what the EXAMPLES and the SPEC say; if the code disagrees with an example, the test MUST
   fail and its message must name the example number. Do not adapt an expectation to the code.
2. Write exactly the card's `targets` (a test file). One test per example when the examples are
   numbered; the docstring names the Function and the example number.
3. Run the card's acceptance from the repository root with `bash -c '<acceptance>'` (read it from
   the JSON, do not retype it). If it fails because the CODE is wrong, do not touch the code: leave
   the failing test in place, and report the card as "judge found a defect" with the example
   number and the assertion message. If it fails because your test is wrong, fix the test.
4. Commit each judge card separately with `git -c commit.gpgsign=false commit`:
     morph <custom_id>: <targets>

     Morph-Card: <custom_id>
     Morph-Model: claude-sonnet-5
     Morph-Acceptance-Exit: <0, or the exit code you left it at>

Constraints: Python 3.9-compatible syntax; unittest with `msg=` on every assertion; never modify a
file outside the current card's targets.

Report: per judge card the acceptance runs, the defects found in the code (example number,
assertion), and `git log --oneline <base>..HEAD`.
```

If the judge found a defect: the code card goes back to the executor **with the text
of the failed assertion**, not with a request to "fix the test". The judge's test is not
changed until the orchestrator has established that the example is wrong, not the code.
