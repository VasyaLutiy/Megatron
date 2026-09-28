"""Acceptance guard for the v6 patch cards (docs/TASK_MEGATRON_V6.md, section 3).

Usage: venv/bin/python decks/v6_guard.py FILE --quotes N --hashes N
                                         (--tests N | --tests-min N)
                                         [--lines A,B-C] [--max 60]

Checks one edited file against HEAD and prints every violation:
- prose: the count of triple double quotes >= N, lines holding '#' >= N
  (v6 adds code, so counts may grow; a dropped docstring still shows as a
  removed line outside --lines);
- tests: the count of 'def test_' equals --tests, or is >= --tests-min;
- deletions: every removed line (git diff -U0 HEAD) is one of --lines,
  old line numbers, single or A-B ranges; none given means additions only;
- envelope: insertions and deletions each <= --max.
A file that is not tracked at HEAD (a new test file) gets only the prose
and test-count checks.
Exit 0 when all hold, 1 otherwise.
"""

import argparse
import re
import subprocess
import sys

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


def parse_lines(spec):
    allowed = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            allowed.update(range(int(a), int(b) + 1))
        else:
            allowed.add(int(part))
    return allowed


def tracked(path):
    return subprocess.run(["git", "cat-file", "-e", "HEAD:" + path],
                          capture_output=True).returncode == 0


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
    ap.add_argument("--tests", type=int)
    ap.add_argument("--tests-min", type=int)
    ap.add_argument("--lines", default="")
    ap.add_argument("--max", type=int, default=60)
    a = ap.parse_args(argv)
    text = open(a.path, encoding="utf-8").read()
    errors = []

    quotes = text.count('"' * 3)
    if quotes < a.quotes:
        errors.append("PROSE GUARD FAILED: %d triple quotes, expected >= %d "
                      "(a docstring was dropped or split)" % (quotes, a.quotes))
    hashes = sum(1 for ln in text.splitlines() if "#" in ln)
    if hashes < a.hashes:
        errors.append("PROSE GUARD FAILED: %d lines with '#', expected >= %d "
                      "(a comment was dropped)" % (hashes, a.hashes))
    tests = len(re.findall(r"^\s*def test_", text, re.M))
    if a.tests is not None and tests != a.tests:
        errors.append("TEST COUNT FAILED: %d test methods, expected %d"
                      % (tests, a.tests))
    if a.tests_min is not None and tests < a.tests_min:
        errors.append("TEST COUNT FAILED: %d test methods, expected >= %d"
                      % (tests, a.tests_min))

    added = 0
    removed = []
    if tracked(a.path):
        allowed = parse_lines(a.lines)
        removed, diff = removed_lines(a.path)
        stray = [n for n in removed if n not in allowed]
        if stray:
            errors.append("DELETION GUARD FAILED: removed old line(s) %s; only "
                          "%s may change" % (stray, a.lines or "none (additions only)"))
        added = sum(1 for ln in diff.splitlines()
                    if ln.startswith("+") and not ln.startswith("+++"))
        if added > a.max or len(removed) > a.max:
            errors.append("ENVELOPE FAILED: +%d/-%d, limit %d"
                          % (added, len(removed), a.max))

    for e in errors:
        print(e)
    if errors:
        return 1
    print("guard ok: %s +%d/-%d, %d triple quotes, %d tests"
          % (a.path, added, len(removed), quotes, tests))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
