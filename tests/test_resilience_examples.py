"""Judge test of TASK_MEGATRON_V6.md, written from the spec only.

Examples proven: P.2, P.3 (partial discover at the search level), T.1, T.2
(storage.existing_logins), R.1, R.2, R.4 (CLI partial discover, exit 3),
K.1, K.2, K.4, K.6 (harvest --skip-existing).
"""

import asyncio
import contextlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from megatron.github_client import GitHubClient, GitHubError
from megatron.search import discover_logins
from megatron.storage import existing_logins, save_experts

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
U1 = "https://api.github.com/search/users?q=followers%3A%3E5000&per_page=30"
QUERY = "followers:>5000"


def make_walk_fake(recorded, fail_on_call=None):
    # type: (list, object) -> object
    """Synthetic search walk of spec section 2.1; raises on call fail_on_call."""
    def fake(url, headers):
        # type: (str, dict) -> tuple
        recorded.append(url)
        if fail_on_call is not None and len(recorded) == fail_on_call:
            raise GitHubError("HTTP 403 for " + url, 403)
        if url == U1:
            page = 1
        else:
            page = int(url.split("&page=")[1])
        body = json.dumps({
            "total_count": 240,
            "incomplete_results": False,
            "items": [{"login": "p%d_u%02d" % (page, i)} for i in range(30)],
        }).encode("utf-8")
        link = "<" + U1 + '&page=%d>; rel="next"' % (page + 1)
        return 200, {"Link": link}, body
    return fake


def walk_logins(pages):
    # type: (int) -> list
    out = []
    for page in range(1, pages + 1):
        out.extend("p%d_u%02d" % (page, i) for i in range(30))
    return out


def run_disc(transport, pages):
    # type: (object, int) -> object
    client = GitHubClient(token="x", transport=transport)
    return asyncio.run(discover_logins(client, QUERY, pages))


def make_fake():
    # type: () -> object
    fixtures = os.path.join(REPO_ROOT, "tests", "fixtures")
    with open(os.path.join(fixtures, "user_torvalds.json"), "rb") as fh:
        user = json.loads(fh.read().decode("utf-8"))
    with open(os.path.join(fixtures, "repos_torvalds.json"), "rb") as fh:
        repos = json.loads(fh.read().decode("utf-8"))
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


def make_recording_fake(recorded):
    # type: (list) -> object
    inner = make_fake()

    async def fake(path):
        # type: (str) -> object
        recorded.append(path)
        return await inner(path)
    return fake


def seed(db_path, logins):
    # type: (str, list) -> None
    from megatron.cli import harvest
    asyncio.run(harvest(list(logins), make_fake(), db_path))


def row_dicts(db_path):
    # type: (str) -> list
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute("SELECT * FROM experts")]
    finally:
        conn.close()


def capture_main(argv, fetch_json=None):
    # type: (list, object) -> tuple
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        from megatron.cli import main
        code = main(argv, fetch_json=fetch_json)
    return code, out.getvalue(), err.getvalue()


class ResilienceExamples(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        # type: () -> None
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db = os.path.join(self._tmp.name, "experts.db")

    # --- search level ---

    def test_p2_walk_raise_on_call_6(self):
        """P example 2: raise on call 6, pages=8 -> 150 logins, pages 5, page 6 failed."""
        recorded = []
        fake = make_walk_fake(recorded, fail_on_call=6)
        client = GitHubClient(token="x", transport=fake)
        result = asyncio.run(discover_logins(client, QUERY, 8))
        self.assertEqual(
            walk_logins(5), result["logins"],
            msg="logins of pages 1..5 in API order",
        )
        self.assertEqual(240, result["total_count"], msg="total_count from page 1")
        self.assertEqual(5, result["pages"], msg="pages fetched")
        self.assertEqual(6, result["failed_page"], msg="failed_page")
        self.assertEqual(403, result["failed_status"], msg="failed_status")
        self.assertEqual(
            6, len(recorded), msg="no request after the failing one",
        )
        self.assertIs(fake, client.transport, msg="transport restored")

    def test_p3_walk_raise_on_call_1(self):
        """P example 3: raise on call 1 -> empty logins, total_count None, page 1 failed."""
        recorded = []
        fake = make_walk_fake(recorded, fail_on_call=1)
        result = run_disc(fake, 8)
        self.assertEqual([], result["logins"], msg="no logins fetched")
        self.assertIsNone(result["total_count"], msg="total_count None when page 1 fails")
        self.assertEqual(0, result["pages"], msg="pages 0")
        self.assertEqual(1, result["failed_page"], msg="failed_page 1")
        self.assertEqual(403, result["failed_status"], msg="failed_status 403")
        self.assertIn("incomplete_results", result, msg="incomplete_results key present")

    # --- storage ---

    def test_t1_fresh_db_gives_empty_set(self):
        """T example 1: existing_logins on a fresh path is set() and never raises."""
        fresh = os.path.join(self._tmp.name, "fresh.db")
        self.assertEqual(set(), existing_logins(fresh), msg="fresh db -> empty set")

    def test_t2_logins_after_save_experts(self):
        """T example 2: save_experts of two records -> their logins; resave is idempotent."""
        source = os.path.join(self._tmp.name, "source.db")
        seed(source, ["torvalds", "minnow"])
        records = row_dicts(source)
        target = os.path.join(self._tmp.name, "target.db")
        save_experts(target, records)
        self.assertEqual(
            {"torvalds", "minnow"}, existing_logins(target),
            msg="logins of the saved records",
        )
        again = [rec for rec in records if rec["login"] == "torvalds"]
        save_experts(target, again)
        self.assertEqual(
            {"torvalds", "minnow"}, existing_logins(target),
            msg="saving torvalds again leaves the same set",
        )

    # --- CLI discover ---

    def test_r1_cli_partial_exit_3(self):
        """R example 1: raise on call 6, --pages 8 -> exit 3, 150 logins, exact stderr."""
        fake = make_walk_fake([], fail_on_call=6)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("megatron.github_client.urllib_transport", fake):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                from megatron.cli import main
                code = main(["discover", QUERY, "--pages", "8"])
        self.assertEqual(3, code, msg="partial discover exits 3")
        self.assertEqual(walk_logins(5), out.getvalue().splitlines(), msg="stdout logins")
        self.assertIn("discovered 150 of 240, pages 5", err.getvalue(), msg="summary line")
        self.assertIn(
            "warning: partial result, page 6 failed: HTTP 403", err.getvalue(),
            msg="partial warning line",
        )
        self.assertNotIn("Traceback", err.getvalue(), msg="no traceback")

    def test_r2_cli_partial_first_page(self):
        """R example 2: raise on call 1 -> exit 3, empty stdout, warning on stderr."""
        fake = make_walk_fake([], fail_on_call=1)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("megatron.github_client.urllib_transport", fake):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                from megatron.cli import main
                code = main(["discover", QUERY, "--pages", "3"])
        self.assertEqual(3, code, msg="partial discover exits 3")
        self.assertEqual("", out.getvalue(), msg="stdout empty")
        self.assertIn(
            "warning: partial result, page 1 failed: HTTP 403", err.getvalue(),
            msg="partial warning line",
        )

    def test_r4_real_process_exit_3_no_traceback(self):
        """R example 4: the motive itself in a subprocess; fake lives inside the child."""
        script = (
            "import json, sys\n"
            "import megatron.github_client as gc\n"
            "from megatron.github_client import GitHubError\n"
            "U1 = %r\n"
            "calls = []\n"
            "def fake(url, headers):\n"
            "    calls.append(url)\n"
            "    if len(calls) == 2:\n"
            "        raise GitHubError('HTTP 403 for ' + url, 403)\n"
            "    page = 1 if url == U1 else int(url.split('&page=')[1])\n"
            "    body = json.dumps({'total_count': 240, 'incomplete_results': False,\n"
            "                       'items': [{'login': 'p%%d_u%%02d' %% (page, i)}\n"
            "                                 for i in range(30)]}).encode('utf-8')\n"
            "    return 200, {'Link': '<' + U1 + '&page=%%d>; rel=\"next\"' %% (page + 1)}, body\n"
            "gc.urllib_transport = fake\n"
            "from megatron.cli import main\n"
            "sys.exit(main(['discover', %r, '--pages', '3']))\n"
        ) % (U1, QUERY)
        proc = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT, capture_output=True,
        )
        self.assertEqual(3, proc.returncode, msg="child exits 3 on partial discover")
        self.assertNotIn(b"Traceback", proc.stderr, msg="no traceback in child stderr")
        self.assertIn(b"page 2 failed: HTTP 403", proc.stderr, msg="warning in child stderr")
        self.assertEqual(
            walk_logins(1), proc.stdout.decode("utf-8").splitlines(),
            msg="child stdout holds page 1 logins",
        )

    # --- CLI harvest --skip-existing ---

    def test_k1_skip_existing_fetches_only_missing(self):
        """K example 1: torvalds pre-seeded; only minnow is fetched."""
        seed(self.db, ["torvalds"])
        fetched = []
        code, out, err = capture_main(
            ["harvest", "torvalds", "minnow", "--db", self.db, "--skip-existing"],
            fetch_json=make_recording_fake(fetched),
        )
        self.assertEqual(0, code, msg="exit code 0")
        self.assertIn("saved 1 of 2", out, msg="stdout saved line")
        self.assertIn("fetched 1, skipped 1, failed 0", out, msg="stdout tally line")
        self.assertNotIn("torvalds", "".join(fetched), msg="torvalds not fetched")
        conn = sqlite3.connect(self.db)
        try:
            rows = conn.execute("SELECT login FROM experts").fetchall()
        finally:
            conn.close()
        self.assertEqual(2, len(rows), msg="db holds 2 rows")

    def test_k2_skip_existing_all_present_no_fetch(self):
        """K example 2: both pre-seeded; fetch_json is never called."""
        seed(self.db, ["torvalds", "minnow"])
        fetched = []
        code, out, err = capture_main(
            ["harvest", "torvalds", "minnow", "--db", self.db, "--skip-existing"],
            fetch_json=make_recording_fake(fetched),
        )
        self.assertEqual(0, code, msg="exit code 0")
        self.assertEqual([], fetched, msg="fetch_json never called")
        self.assertIn("saved 0 of 2", out, msg="stdout saved line")
        self.assertIn("fetched 0, skipped 2, failed 0", out, msg="stdout tally line")

    def test_k4_skip_existing_with_failure(self):
        """K example 4: torvalds pre-seeded, failing fake -> exit 1, failed: minnow."""
        seed(self.db, ["torvalds"])
        code, out, err = capture_main(
            ["harvest", "torvalds", "minnow", "--db", self.db, "--skip-existing"],
            fetch_json=make_failing_fake(),
        )
        self.assertEqual(1, code, msg="exit code 1 when one failed")
        self.assertIn("fetched 1, skipped 1, failed 1", out, msg="stdout tally line")
        self.assertIn("failed: minnow", err, msg="stderr failed line")

    def test_k6_harvest_dict_with_skipped(self):
        """K example 6: harvest(..., skip_existing=True) result dict shape."""
        seed(self.db, ["torvalds"])
        from megatron.cli import harvest
        result = asyncio.run(
            harvest(["torvalds", "minnow"], make_fake(), self.db, skip_existing=True)
        )
        self.assertEqual(
            {"requested": 2, "saved": 1, "failed": [], "skipped": ["torvalds"]},
            result, msg="harvest result with skipped",
        )


if __name__ == "__main__":
    unittest.main()
