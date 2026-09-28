"""CLI acceptance for `megatron discover` (spec examples C.1-C.5)."""

import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

from megatron.github_client import GitHubClient

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

U1 = "https://api.github.com/search/users?q=followers%3A%3E5000&per_page=30"
U2 = "https://api.github.com/search/users?q=followers%3A%3E5000&per_page=30&page=2"
UE = "https://api.github.com/search/users?q=followers%3A%3E100000000&per_page=30"

ROUTES = {
    U1: ("search_page1.json", "search_page1.headers.txt"),
    U2: ("search_page2.json", "search_page2.headers.txt"),
    UE: ("search_empty.json", "search_empty.headers.txt"),
}


def parse_headers(path):
    headers = {}
    with open(path, "r") as handle:
        lines = handle.read().split("\n")
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        name, _, value = line.partition(": ")
        headers[name] = value
    return headers


def load_logins(name):
    with open(os.path.join(FIXTURES, name), "rb") as handle:
        data = json.loads(handle.read().decode("utf-8"))
    return [item["login"] for item in data["items"]]


def make_fake_transport(recorded, overrides=None):
    def fake(url, headers):
        recorded.append(url)
        override = (overrides or {}).get(url)
        if override is not None:
            return 200, dict(override[0]), override[1]
        if url not in ROUTES:
            return 404, {}, b'{"message": "Not Found"}'
        body_name, headers_name = ROUTES[url]
        with open(os.path.join(FIXTURES, body_name), "rb") as handle:
            body = handle.read()
        return 200, parse_headers(os.path.join(FIXTURES, headers_name)), body

    return fake


class CliDiscoverTestCase(unittest.TestCase):
    maxDiff = None

    def run_main(self, argv, overrides=None):
        recorded = []
        fake = make_fake_transport(recorded, overrides)
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch(
            "megatron.github_client.urllib_transport", fake
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            from megatron.cli import main

            code = main(argv)
        return code, stdout.getvalue(), stderr.getvalue(), recorded

    def test_C1_two_pages_prints_60_logins_in_order(self):
        """C example 1: --pages 2 prints L1+L2 in API order."""
        expected = load_logins("search_page1.json") + load_logins("search_page2.json")
        code, out, err, recorded = self.run_main(
            ["discover", "followers:>5000", "--pages", "2"]
        )
        self.assertEqual(0, code, msg="exit code")
        self.assertEqual(expected, out.splitlines(), msg="stdout lines")
        self.assertIn("discovered 60 of 1230, pages 2", err, msg="stderr summary")
        self.assertEqual([U1, U2], recorded, msg="transport urls")

    def test_C2_default_one_page(self):
        """C example 2: --pages omitted prints L1, one request."""
        expected = load_logins("search_page1.json")
        code, out, err, recorded = self.run_main(["discover", "followers:>5000"])
        self.assertEqual(0, code, msg="exit code")
        self.assertEqual(expected, out.splitlines(), msg="stdout lines")
        self.assertIn("discovered 30 of 1230, pages 1", err, msg="stderr summary")
        self.assertEqual([U1], recorded, msg="transport urls")

    def test_C3_empty_query(self):
        """C example 3: empty result prints nothing, summary on stderr."""
        code, out, err, recorded = self.run_main(
            ["discover", "followers:>100000000", "--pages", "1"]
        )
        self.assertEqual(0, code, msg="exit code")
        self.assertEqual("", out, msg="stdout empty")
        self.assertIn("discovered 0 of 0, pages 1", err, msg="stderr summary")
        self.assertEqual([UE], recorded, msg="transport urls")

    def test_C4_incomplete_results_warning(self):
        """C example 4: incomplete_results true emits the warning."""
        with open(os.path.join(FIXTURES, "search_page1.json"), "rb") as handle:
            data = json.loads(handle.read().decode("utf-8"))
        data["incomplete_results"] = True
        body = json.dumps(data).encode("utf-8")
        headers = parse_headers(os.path.join(FIXTURES, "search_page1.headers.txt"))
        expected = load_logins("search_page1.json")
        code, out, err, recorded = self.run_main(
            ["discover", "followers:>5000", "--pages", "1"],
            overrides={U1: (headers, body)},
        )
        self.assertEqual(0, code, msg="exit code")
        self.assertEqual(expected, out.splitlines(), msg="stdout lines")
        self.assertIn("warning: incomplete_results", err, msg="warning on stderr")
        self.assertIn("discovered 30 of 1230, pages 1", err, msg="stderr summary")

    def test_C5_help_paths(self):
        """C example 5: `discover --help` and `harvest --help` exit 0."""
        proc = subprocess.run(
            [sys.executable, "-m", "megatron", "discover", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
        )
        self.assertEqual(0, proc.returncode, msg="discover --help exit code")
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            from megatron.cli import main

            with self.assertRaises(SystemExit) as ctx:
                main(["harvest", "--help"])
        self.assertEqual(0, ctx.exception.code, msg="harvest --help exit code")


if __name__ == "__main__":
    unittest.main()
