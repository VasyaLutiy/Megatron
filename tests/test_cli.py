"""Examples B.1-B.4 of TASK_MEGATRON_V2.md: the harvest CLI."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

from megatron.cli import harvest, main
from megatron.storage import top_experts

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name):
    # type: (str) -> dict
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def make_fake():
    # type: () -> object
    user = load("user_torvalds.json")
    repos = load("repos_torvalds.json")
    minnow = dict(user)
    minnow["login"] = "minnow"
    minnow["followers"] = 7

    async def fake(path):
        # type: (str) -> object
        if path == "/users/torvalds":
            return dict(user)
        if path == "/users/torvalds/repos?per_page=100":
            return [dict(r) for r in repos]
        if path == "/users/minnow":
            return dict(minnow)
        if path == "/users/minnow/repos?per_page=100":
            return []
        raise ValueError("unexpected path: " + path)

    return fake


def make_failing_fake():
    # type: () -> object
    inner = make_fake()

    async def fake(path):
        # type: (str) -> object
        if "minnow" in path:
            raise ValueError("no such user")
        return await inner(path)

    return fake


class HarvestTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        # type: () -> None
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db = os.path.join(self._tmp.name, "experts.db")

    def test_b1_harvest_saves_two_experts(self):
        """B example 1: harvest over two good logins saves both."""
        result = self._run(harvest(["torvalds", "minnow"], make_fake(), self.db))
        self.assertEqual(
            {"requested": 2, "saved": 2, "failed": []},
            result,
            msg="harvest result dict wrong",
        )
        top = top_experts(self.db, 2)
        self.assertEqual(
            ["torvalds", "minnow"],
            [rec["login"] for rec in top],
            msg="ranked logins wrong",
        )
        self.assertEqual(
            [1635, 90],
            [rec["expertise_score"] for rec in top],
            msg="ranked scores wrong",
        )

    def test_b2_harvest_reports_failed_login(self):
        """B example 2: a login whose fetch raises lands in failed."""
        result = self._run(harvest(["torvalds", "minnow"], make_failing_fake(), self.db))
        self.assertEqual(
            {"requested": 2, "saved": 1, "failed": ["minnow"]},
            result,
            msg="harvest result with a failure wrong",
        )
        self.assertEqual(
            1, len(top_experts(self.db, 10)), msg="table should hold 1 row"
        )

    def test_b3_main_exit_codes_and_output(self):
        """B example 3: main returns 0/1 and prints to stdout/stderr."""
        out, err, code = self._capture(
            main, ["harvest", "torvalds", "minnow", "--db", self.db], make_fake()
        )
        self.assertEqual(0, code, msg="exit code should be 0 when all saved")
        self.assertIn("saved 2 of 2", out.getvalue(), msg="stdout line missing")
        out, err, code = self._capture(
            main, ["harvest", "torvalds", "minnow", "--db", self.db],
            make_failing_fake(),
        )
        self.assertEqual(1, code, msg="exit code should be 1 when one failed")
        self.assertIn("saved 1 of 2", out.getvalue(), msg="stdout line missing")
        self.assertIn("failed: minnow", err.getvalue(), msg="stderr line missing")

    def test_b4_module_help_via_subprocess(self):
        """B example 4: `python -m megatron harvest --help` exits 0."""
        proc = subprocess.run(
            [sys.executable, "-m", "megatron", "harvest", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
        )
        self.assertEqual(0, proc.returncode, msg="--help should exit 0")

    @staticmethod
    def _run(coro):
        # type: (object) -> object
        import asyncio

        return asyncio.run(coro)

    @staticmethod
    def _capture(fn, argv, fetch_json):
        # type: (object, list, object) -> tuple
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = fn(argv, fetch_json=fetch_json)
        return out, err, code


if __name__ == "__main__":
    unittest.main()
