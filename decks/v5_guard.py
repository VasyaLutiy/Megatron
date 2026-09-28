"""Acceptance guard for the v5 patch cards (docs/TASK_MEGATRON_V5.md, section 3).

Usage: venv/bin/python decks/v5_guard.py FILE --quotes N --hashes N --tests N
                                         --lines A,B,C [--max 60]

Checks one edited file against HEAD and prints every violation:
- prose: the count of triple double quotes equals N, lines holding '#' >= N;
- tests: the count of 'def test_' equals N (no test added or dropped);
- deletions: every removed line (git diff -U0 HEAD) is one of --lines,
  the old line numbers that hold the old formula or an old score;
- envelope: insertions and deletions each <= --max;
- old values: none of 850302, 850316, 850330, 341138, the linear formula
  or the old minnow score 7 is left in the file.
Exit 0 when all hold, 1 otherwise.
"""

import argparse
import re
import subprocess
import sys

OLD = re.compile(r"850302|850316|850330|341138|\+ ?2 ?\* ?total_stars|2 ?\* ?262418|2 ?\* ?0\b"
                 r"|-> 7\b|expertise_score 7\b|\"expertise_score\"\], 7\b")
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


def removed_lines(path):
    out = subprocess.run(["git", "diff", "-U0", "HEAD", "--", path],
                         capture_output=True, text=True, check=True).stdout
    removed = []
    for line in out.splitlines():
        m = HUNK.match(line)
        if m:
            start, count = int(m.group(1)), int(m.group(2) or "1")
            removed.extend(range(start, start + count))
    return removed, out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--quotes", type=int, required=True)
    ap.add_argument("--hashes", type=int, required=True)
    ap.add_argument("--tests", type=int, required=True)
    ap.add_argument("--lines", required=True)
    ap.add_argument("--max", type=int, default=60)
    a = ap.parse_args(argv)
    text = open(a.path, encoding="utf-8").read()
    errors = []

    quotes = text.count('"' * 3)
    if quotes != a.quotes:
        errors.append("PROSE GUARD FAILED: %d triple quotes, expected %d "
                      "(a docstring was dropped or split)" % (quotes, a.quotes))
    hashes = sum(1 for ln in text.splitlines() if "#" in ln)
    if hashes < a.hashes:
        errors.append("PROSE GUARD FAILED: %d lines with '#', expected >= %d "
                      "(a comment was dropped)" % (hashes, a.hashes))
    tests = len(re.findall(r"^\s*def test_", text, re.M))
    if tests != a.tests:
        errors.append("TEST COUNT FAILED: %d test methods, expected %d"
                      % (tests, a.tests))

    allowed = set(int(x) for x in a.lines.split(",") if x)
    removed, diff = removed_lines(a.path)
    stray = [n for n in removed if n not in allowed]
    if stray:
        errors.append("DELETION GUARD FAILED: removed old line(s) %s; only %s "
                      "may change" % (stray, sorted(allowed)))
    added = sum(1 for ln in diff.splitlines()
                if ln.startswith("+") and not ln.startswith("+++"))
    if added > a.max or len(removed) > a.max:
        errors.append("ENVELOPE FAILED: +%d/-%d, limit %d"
                      % (added, len(removed), a.max))

    for i, ln in enumerate(text.splitlines(), 1):
        if OLD.search(ln):
            errors.append("OLD VALUE LEFT: %s:%d: %s" % (a.path, i, ln.strip()))

    for e in errors:
        print(e)
    if errors:
        return 1
    print("guard ok: %s +%d/-%d, %d triple quotes, %d tests"
          % (a.path, added, len(removed), quotes, tests))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
