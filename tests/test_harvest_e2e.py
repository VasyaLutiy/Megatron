"""End-to-end tests: GitHubClient + cli.harvest, fully offline (PaukMegatron v2.0).

Proves spec section 3 examples D.1 and D.2. No test opens a network
connection: the transport seam is faked with a plain function.
"""

import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from megatron.cli import main
from megatron.github_client import GitHubClient
from megatron import storage


FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def read_bytes(name):
    # type: (str) -> bytes
    with open(os.path.join(FIXTURES, name), "rb") as handle:
        return handle.read()


def parse_headers(name):
    # type: (str) -> dict
    """Parse a .headers.txt fixture: skip status line, split at first ': '."""
    headers = {}
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        name_part, sep, value_part = line.partition(": ")
        if sep:
            headers[name_part.strip()] = value_part.strip()
    return headers


def make_transport():
    # type: () -> object
    """Build a fake transport keyed by full URL; records (url, headers)."""
    table = {
        "https://api.github.com/users/torvalds": (
            200,
            parse_headers("rate_limit_headers.txt"),
            read_bytes("user_torvalds.json"),
        ),
        "https://api.github.com/users/torvalds/repos?per_page=100": (
            200,
            parse_headers("repos_torvalds_page1.headers.txt"),
            read_bytes("repos_torvalds_page1.json"),
        ),
        "https://api.github.com/user/1024025/repos?per_page=5&page=2": (
            200,
            parse_headers("repos_torvalds_page2.headers.txt"),
            read_bytes("repos_torvalds_page2.json"),
        ),
        "https://api.github.com/user/1024025/repos?per_page=5&page=3": (
            200,
            parse_headers("repos_torvalds_page3.headers.txt"),
            read_bytes("repos_torvalds_page3.json"),
        ),
    }
    calls = []

    def transport(url, headers):
        # type: (str, dict) -> tuple
        calls.append((url, dict(headers)))
        if url not in table:
            raise AssertionError("fake transport got unknown URL: %s" % url)
        return table[url]

    transport.calls = calls  # type: ignore[attr-defined]
    return transport


def get_header(headers, name):
    # type: (dict, str) -> object
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


class HarvestEndToEndTest(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        # type: () -> None
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db = os.path.join(self._tmp.name, "experts.db")

    def test_d1_full_pipeline_scores_all_pages(self):
        # type: () -> None
        """D example 1: harvest torvalds offline, 4 calls, 262425 / 1635."""
        fake = make_transport()
        client = GitHubClient(token="x", transport=fake)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(
                ["harvest", "torvalds", "--db", self.db],
                fetch_json=client.fetch_json,
            )
        self.assertEqual(code, 0, msg="main should exit 0 (got stdout=%r stderr=%r)" % (out.getvalue(), err.getvalue()))
        self.assertEqual(
            len(fake.calls), 4,
            msg="transport should be called 4 times (user + 3 repo pages), got %r" % (fake.calls,),
        )
        self.assertEqual(
            [url for url, _ in fake.calls],
            [
                "https://api.github.com/users/torvalds",
                "https://api.github.com/users/torvalds/repos?per_page=100",
                "https://api.github.com/user/1024025/repos?per_page=5&page=2",
                "https://api.github.com/user/1024025/repos?per_page=5&page=3",
            ],
            msg="transport call URLs should be user then page 1 then the link URLs",
        )
        top = storage.top_experts(self.db, 1)
        self.assertEqual(len(top), 1, msg="expected exactly 1 expert row")
        record = top[0]
        self.assertEqual(
            record["login"], "torvalds",
            msg="expert login should be torvalds, got %r" % (record["login"],),
        )
        self.assertEqual(
            record["total_stars"], 262425,
            msg="total_stars over all 3 pages should be 262425 (a single page would give 7836); got %r" % (record["total_stars"],),
        )
        self.assertEqual(
            record["expertise_score"], 1635,
            msg="expertise_score over all 3 pages should be 1635 (a single page would give 1330); got %r" % (record["expertise_score"],),
        )

    def test_d2_main_builds_client_and_sends_token(self):
        # type: () -> None
        """D example 2: main without fetch_json uses patched transport + env token."""
        fake = make_transport()
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("megatron.github_client.urllib_transport", fake), \
                mock.patch.dict(os.environ, {"GITHUB_TOKEN": "envtok"}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["harvest", "torvalds", "--db", self.db])
        self.assertEqual(code, 0, msg="main should exit 0 without an injected fetch_json")
        self.assertTrue(fake.calls, msg="the patched urllib_transport was never called")
        for url, headers in fake.calls:
            self.assertEqual(
                get_header(headers, "Authorization"), "Bearer envtok",
                msg="every call to %s should carry Authorization: Bearer envtok, headers=%r" % (url, headers),
            )
        top = storage.top_experts(self.db, 1)
        self.assertEqual(len(top), 1, msg="expected exactly 1 expert row")
        self.assertEqual(
            top[0]["expertise_score"], 1635,
            msg="expertise_score should still be 1635 via the built-in client, got %r" % (top[0]["expertise_score"],),
        )


if __name__ == "__main__":
    unittest.main()
