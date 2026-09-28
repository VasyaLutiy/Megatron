"""Examples R.1-R.4 and K.1-K.6 of docs/TASK_MEGATRON_V6.md: resilient CLI.

R.* prove the partial `discover` result (a GitHubError on a search page
keeps the logins of the earlier pages, exit code 3, no traceback);
K.* prove `harvest --skip-existing` against a pre-seeded db.
"""

import asyncio
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from megatron.cli import harvest, main
from megatron.github_client import GitHubError
from megatron.storage import top_experts

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

U1 = "https://api.github.com/search/users?q=followers%3A%3E5000&per_page=30"

_R4_SCRIPT = """import json
import sys
import megatron.github_client as gc

U1 = "https://api.github.com/search/users?q=followers%3A%3E5000&per_page=30"
calls = []


def fake(url, headers):
    calls.append(url)
    if len(calls) == 2:
        raise gc.GitHubError("HTTP 403 for " + url, 403)
    if url == U1:
        k = 1
    else:
        k = int(url[len(U1) + 6:])
    body = json.dumps({
        "total_count": 240,
        "incomplete_results": False,
        "items": [{"login": "p%d_u%02d" % (k, i)} for i in range(30)],
    }).encode("utf-8")
    link = "<" + U1 + "&page=%d>; rel=\\"next\\"" % (k + 1)
    return 200, {"Link": link}, body


gc.urllib_transport = fake
from megatron.cli import main

sys.exit(main(["discover", "followers:>5000", "--pages", "3"]))
"""


def load(name):
    # type: (str) -> dict
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def make_fetch(recorded):
    # type: (object) -> object
    """Fake fetch_json over the user fixtures; records every path."""
    user = load("user_torvalds.json")
    repos = load("repos_torvalds.json")
    minnow = dict(user)
    minnow["login"] = "minnow"
    minnow["followers"] = 7

    async def fake(path):
        # type: (str) -> object
        if recorded is not None:
            recorded.append(path)
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


def make_failing_fetch(recorded):
    # type: (object) -> object
    inner = make_fetch(recorded)

    async def fake(path):
        # type: (str) -> object
        if "minnow" in path:
            raise ValueError("no such user")
        return await inner(path)

    return fake


def make_walk_transport(recorded, fail_on=None):
    # type: (list, object) -> object
    """Synthetic search walk of section 2.1: 30 logins per page.

    Counts its calls; on call number fail_on it raises GitHubError 403
    instead of answering.
    """
    def fake(url, headers):
        # type: (str, dict) -> tuple
        recorded.append(url)
        if fail_on is not None and len(recorded) == fail_on:
            raise GitHubError("HTTP 403 for " + url, 403)
        if url == U1:
            k = 1
        else:
            k = int(url[len(U1) + len("&page="):])
        body = json.dumps(
            {
                "total_count": 240,
                "incomplete_results": False,
                "items": [{"login": "p%d_u%02d" % (k, i)} for i in range(30)],
            }
        ).encode("utf-8")
        link = "<" + U1 + "&page=%d>; rel=\"next\"" % (k + 1)
        return 200, {"Link": link}, body

    return fake


def walk_logins(pages):
    # type: (int) -> list
    return [
        "p%d_u%02d" % (k, i) for k in range(1, pages + 1) for i in range(30)
    ]


class DiscoverPartialTests(unittest.TestCase):
    maxDiff = None

    def run_discover(self, argv, fail_on=None):
        # type: (list, object) -> tuple
        recorded = []
        fake = make_walk_transport(recorded, fail_on)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch(
            "megatron.github_client.urllib_transport", fake
        ), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue(), recorded

    def test_r1_partial_discover_keeps_earlier_pages(self):
        """R example 1: raise on call 6, --pages 8 -> 150 logins, exit 3."""
        code, out, err, recorded = self.run_discover(
            ["discover", "followers:>5000", "--pages", "8"], fail_on=6
        )
        self.assertEqual(3, code, msg="exit code should be 3 on a partial result")
        self.assertEqual(walk_logins(5), out.splitlines(), msg="stdout logins")
        self.assertEqual(6, len(recorded), msg="transport calls")
        self.assertIn("discovered 150 of 240, pages 5", err, msg="stderr summary")
        self.assertIn(
            "warning: partial result, page 6 failed: HTTP 403",
            err,
            msg="partial warning missing",
        )
        self.assertNotIn("Traceback", err, msg="traceback leaked")

    def test_r2_partial_on_first_page(self):
        """R example 2: raise on call 1 -> no logins, exit 3, warning."""
        code, out, err, recorded = self.run_discover(
            ["discover", "followers:>5000", "--pages", "3"], fail_on=1
        )
        self.assertEqual(3, code, msg="exit code should be 3")
        self.assertEqual("", out, msg="stdout should be empty")
        self.assertEqual(1, len(recorded), msg="transport calls")
        self.assertIn(
            "warning: partial result, page 1 failed: HTTP 403",
            err,
            msg="partial warning missing",
        )

    def test_r3_full_discover_has_no_partial_warning(self):
        """R example 3: no failure, --pages 3 -> exit 0, 90 logins."""
        code, out, err, recorded = self.run_discover(
            ["discover", "followers:>5000", "--pages", "3"]
        )
        self.assertEqual(0, code, msg="exit code")
        self.assertEqual(walk_logins(3), out.splitlines(), msg="stdout logins")
        self.assertEqual(3, len(recorded), msg="transport calls")
        self.assertNotIn("partial", err, msg="no partial warning expected")

    def test_r4_partial_discover_in_real_process(self):
        """R example 4: the motive itself in a child process, no network."""
        proc = subprocess.run(
            [sys.executable, "-c", _R4_SCRIPT],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(3, proc.returncode, msg="child exit code")
        self.assertNotIn("Traceback", proc.stderr, msg="traceback in child stderr")
        self.assertIn(
            "page 2 failed: HTTP 403", proc.stderr, msg="partial warning in child"
        )
        self.assertEqual(
            walk_logins(1), proc.stdout.splitlines(), msg="child stdout logins"
        )


class HarvestSkipTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        # type: () -> None
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db = os.path.join(self._tmp.name, "experts.db")

    def _capture(self, argv, fetch_json):
        # type: (list, object) -> tuple
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(argv, fetch_json=fetch_json)
        return out.getvalue(), err.getvalue(), code

    def test_k1_skip_existing_fetches_only_the_missing_login(self):
        """K example 1: torvalds pre-seeded, skip-existing over two logins."""
        asyncio.run(harvest(["torvalds"], make_fetch(None), self.db))
        recorded = []
        out, err, code = self._capture(
            ["harvest", "torvalds", "minnow", "--db", self.db, "--skip-existing"],
            make_fetch(recorded),
        )
        self.assertEqual(0, code, msg="exit code")
        self.assertIn("saved 1 of 2", out, msg="saved line")
        self.assertIn("fetched 1, skipped 1, failed 0", out, msg="fetched line")
        self.assertFalse(
            any("torvalds" in path for path in recorded),
            msg="torvalds must not be fetched again",
        )
        rows = top_experts(self.db, 10)
        self.assertEqual(2, len(rows), msg="db should hold 2 rows")
        self.assertEqual(
            ["minnow", "torvalds"],
            sorted(rec["login"] for rec in rows),
            msg="stored logins",
        )

    def test_k2_skip_existing_fetches_nothing_when_all_present(self):
        """K example 2: both pre-seeded -> fetch_json never called."""
        asyncio.run(harvest(["torvalds", "minnow"], make_fetch(None), self.db))
        recorded = []
        out, err, code = self._capture(
            ["harvest", "torvalds", "minnow", "--db", self.db, "--skip-existing"],
            make_fetch(recorded),
        )
        self.assertEqual(0, code, msg="exit code")
        self.assertEqual([], recorded, msg="no fetch for known logins")
        self.assertIn("saved 0 of 2", out, msg="saved line")
        self.assertIn("fetched 0, skipped 2, failed 0", out, msg="fetched line")

    def test_k3_without_flag_both_are_fetched(self):
        """K example 3: torvalds pre-seeded, no flag -> both fetched."""
        asyncio.run(harvest(["torvalds"], make_fetch(None), self.db))
        recorded = []
        out, err, code = self._capture(
            ["harvest", "torvalds", "minnow", "--db", self.db],
            make_fetch(recorded),
        )
        self.assertEqual(0, code, msg="exit code")
        self.assertIn("fetched 2, skipped 0, failed 0", out, msg="fetched line")
        self.assertIn("/users/minnow", recorded, msg="minnow fetched")
        self.assertIn("/users/torvalds", recorded, msg="torvalds fetched")

    def test_k4_skip_existing_with_a_failing_login(self):
        """K example 4: torvalds skipped, minnow fails -> exit 1."""
        asyncio.run(harvest(["torvalds"], make_fetch(None), self.db))
        recorded = []
        out, err, code = self._capture(
            ["harvest", "torvalds", "minnow", "--db", self.db, "--skip-existing"],
            make_failing_fetch(recorded),
        )
        self.assertEqual(1, code, msg="exit code on a failed login")
        self.assertIn("fetched 1, skipped 1, failed 1", out, msg="fetched line")
        self.assertIn("failed: minnow", err, msg="stderr line")

    def test_k5_skip_existing_on_a_fresh_db(self):
        """K example 5: fresh db path -> nothing skipped, all fetched."""
        recorded = []
        out, err, code = self._capture(
            ["harvest", "torvalds", "minnow", "--db", self.db, "--skip-existing"],
            make_fetch(recorded),
        )
        self.assertEqual(0, code, msg="exit code")
        self.assertIn("fetched 2, skipped 0, failed 0", out, msg="fetched line")

    def test_k6_harvest_result_dict_with_skip_existing(self):
        """K example 6: harvest() with skip_existing=True returns 4 keys."""
        asyncio.run(harvest(["torvalds"], make_fetch(None), self.db))
        recorded = []
        result = asyncio.run(
            harvest(
                ["torvalds", "minnow"], make_fetch(recorded), self.db,
                skip_existing=True,
            )
        )
        self.assertEqual(
            {"requested": 2, "saved": 1, "failed": [], "skipped": ["torvalds"]},
            result,
            msg="harvest result dict wrong",
        )
        self.assertFalse(
            any("torvalds" in path for path in recorded),
            msg="torvalds must not be fetched again",
        )


if __name__ == "__main__":
    unittest.main()
