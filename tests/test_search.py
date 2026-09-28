"""Examples P, Q, D of docs/TASK_MEGATRON_V4.md for megatron.search."""

import asyncio
import json
import os
import unittest

from megatron import search
from megatron.github_client import GitHubClient, GitHubError

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

Q = "followers:>5000"
U1 = "https://api.github.com/search/users?q=followers%3A%3E5000&per_page=30"
U2 = (
    "https://api.github.com/search/users?q=followers%3A%3E5000"
    "&per_page=30&page=2"
)
U_EMPTY = (
    "https://api.github.com/search/users?q=followers%3A%3E100000000"
    "&per_page=30"
)


def load_body(name):
    # type: (str) -> bytes
    with open(os.path.join(FIXTURES, name), "rb") as handle:
        return handle.read()


def load_headers(name):
    # type: (str) -> dict
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as handle:
        text = handle.read()
    headers = {}
    for line in text.splitlines()[1:]:
        line = line.strip()
        if not line or ": " not in line:
            continue
        key, value = line.split(": ", 1)
        headers[key] = value
    return headers


def fixture_logins(name):
    # type: (str) -> list
    data = json.loads(load_body(name).decode("utf-8"))
    return [item["login"] for item in data["items"]]


L1 = fixture_logins("search_page1.json")
L2 = fixture_logins("search_page2.json")
H1 = load_headers("search_page1.headers.txt")
H2 = load_headers("search_page2.headers.txt")
H_EMPTY = load_headers("search_empty.headers.txt")


def make_fake(routes, seen):
    # type: (dict, list) -> object
    def fake(url, headers):
        # type: (str, dict) -> tuple
        seen.append(url)
        if url in routes:
            body, resp_headers = routes[url]
            return 200, dict(resp_headers), body
        return 404, {}, b'{"message": "Not Found"}'

    return fake


class TestEncodeQueryAndUrl(unittest.TestCase):
    maxDiff = None

    def test_Q_1(self):
        """Q example 1: encode_query and search_url match GitHub's form."""
        self.assertEqual(
            search.encode_query("followers:>5000"),
            "followers%3A%3E5000",
            msg="encode_query must percent-encode : and >")
        self.assertEqual(
            search.encode_query("language:python followers:>5000"),
            "language%3Apython%20followers%3A%3E5000",
            msg="encode_query must percent-encode the space")
        self.assertEqual(
            search.encode_query("a-b_c.d~e"),
            "a-b_c.d~e",
            msg="unreserved characters are kept")
        self.assertEqual(search.search_url(Q), U1,
                         msg="search_url default per_page is 30")
        self.assertEqual(search.search_url(Q, 30) + "&page=2", U2,
                         msg="search_url(..., 30) + &page=2 is U2")

    def test_Q_2(self):
        """Q example 2: unreserved characters survive encoding."""
        self.assertEqual(
            search.encode_query("a-b_c.d~e"),
            "a-b_c.d~e",
            msg="A-Z a-z 0-9 - . _ ~ are kept byte for byte")


class TestParseSearchPage(unittest.TestCase):
    maxDiff = None

    def test_P_1(self):
        """P example 1: page 1 parses to its 30 logins in item order."""
        data = json.loads(load_body("search_page1.json").decode("utf-8"))
        result = search.parse_search_page(data)
        self.assertEqual(
            result,
            {"logins": L1, "total_count": 1230,
             "incomplete_results": False},
            msg="page 1 must parse to its full login list")
        self.assertEqual(L1[:3], ["torvalds", "karpathy", "claude"],
                         msg="page 1 starts torvalds, karpathy, claude")
        self.assertEqual(L1[29], "geohot", msg="page 1 ends geohot")
        self.assertEqual(len(L1), 30, msg="page 1 has 30 logins")

    def test_P_2(self):
        """P example 2: page 2 parses to its 30 logins in item order."""
        data = json.loads(load_body("search_page2.json").decode("utf-8"))
        result = search.parse_search_page(data)
        self.assertEqual(
            result,
            {"logins": L2, "total_count": 1230,
             "incomplete_results": False},
            msg="page 2 must parse to its full login list")
        self.assertEqual(L2[:3], ["mattpocock", "Microsoft-corp", "getify"],
                         msg="page 2 starts mattpocock, Microsoft-corp, "
                             "getify")
        self.assertEqual(L2[29], "pewdiepie-archdaemon",
                         msg="page 2 ends pewdiepie-archdaemon")

    def test_P_3(self):
        """P example 3: the empty page parses to no logins."""
        data = json.loads(load_body("search_empty.json").decode("utf-8"))
        self.assertEqual(
            search.parse_search_page(data),
            {"logins": [], "total_count": 0, "incomplete_results": False},
            msg="empty page parses to zero logins")

    def test_P_4(self):
        """P example 4: the v1 fixture and an incomplete_results copy."""
        data = json.loads(
            load_body("search_users_python.json").decode("utf-8"))
        self.assertEqual(
            search.parse_search_page(data),
            {"logins": ["karpathy", "openai", "google", "huggingface",
                        "rafaballerini"],
             "total_count": 1746, "incomplete_results": False},
            msg="v1 fixture parses to its five logins, total 1746")
        page1 = json.loads(load_body("search_page1.json").decode("utf-8"))
        page1["incomplete_results"] = True
        self.assertTrue(search.parse_search_page(page1)["incomplete_results"],
                        msg="incomplete_results true is read as True")


class TestDiscoverLogins(unittest.TestCase):
    maxDiff = None

    def run_discover(self, fake, query, pages):
        # type: (object, str, int) -> dict
        client = GitHubClient(token="x", transport=fake)
        return asyncio.run(
            search.discover_logins(client, query, pages)), client

    def test_D_1(self):
        """D example 1: pages=2 walks U1 then U2 and keeps API order."""
        seen = []
        fake = make_fake({U1: (load_body("search_page1.json"), H1),
                          U2: (load_body("search_page2.json"), H2)}, seen)
        result, client = self.run_discover(fake, Q, 2)
        self.assertEqual(
            result,
            {"logins": L1 + L2, "total_count": 1230,
             "incomplete_results": False, "pages": 2},
            msg="pages=2 concatenates L1 + L2 in API order")
        self.assertEqual(len(result["logins"]), 60,
                         msg="two pages give 60 logins")
        self.assertEqual(seen, [U1, U2],
                         msg="transport is called with U1 then U2 verbatim")
        del client

    def test_D_2(self):
        """D example 2: pages=1 fetches only U1."""
        seen = []
        fake = make_fake({U1: (load_body("search_page1.json"), H1),
                          U2: (load_body("search_page2.json"), H2)}, seen)
        result, client = self.run_discover(fake, Q, 1)
        self.assertEqual(
            result,
            {"logins": L1, "total_count": 1230,
             "incomplete_results": False, "pages": 1},
            msg="pages=1 returns only page 1's logins")
        self.assertEqual(seen, [U1], msg="only U1 is fetched")
        del client

    def test_D_3(self):
        """D example 3: the empty query stops after one page."""
        seen = []
        fake = make_fake({U_EMPTY: (load_body("search_empty.json"),
                                    H_EMPTY)}, seen)
        result, client = self.run_discover(fake, "followers:>100000000", 3)
        self.assertEqual(
            result,
            {"logins": [], "total_count": 0, "incomplete_results": False,
             "pages": 1},
            msg="an empty first page ends the walk at pages 1")
        self.assertEqual(seen, [U_EMPTY], msg="only the empty URL is fetched")
        del client

    def test_D_4(self):
        """D example 4: the search rate limit is waited on via the client."""
        seen = []
        sleeps = []
        headers1 = dict(H1)
        headers1["x-ratelimit-remaining"] = "0"
        fake = make_fake({U1: (load_body("search_page1.json"), headers1),
                          U2: (load_body("search_page2.json"), H2)}, seen)

        async def rec(seconds):
            # type: (int) -> None
            sleeps.append((seconds, len(seen)))

        client = GitHubClient(token="x", transport=fake, sleep=rec,
                              clock=lambda: 1790599575)
        result = asyncio.run(search.discover_logins(client, Q, 2))
        self.assertEqual(sleeps, [(60, 1)],
                         msg="exactly one sleep of 60, after request 1 "
                             "before request 2")
        self.assertEqual(
            client.rate_limit,
            {"limit": 10, "remaining": 8, "reset": 1790599635},
            msg="client rate-limit state comes from page 2's headers")
        self.assertEqual(result["pages"], 2, msg="two pages are walked")

    def test_D_5(self):
        """D example 5: the original transport is restored, also on error."""
        seen = []
        fake = make_fake({U1: (load_body("search_page1.json"), H1),
                          U2: (load_body("search_page2.json"), H2)}, seen)
        result, client = self.run_discover(fake, Q, 2)
        self.assertTrue(client.transport is fake,
                        msg="after success client.transport is the original")
        seen2 = []
        fake2 = make_fake({U1: (load_body("search_page1.json"), H1)}, seen2)
        client2 = GitHubClient(token="x", transport=fake2)
        with self.assertRaises(GitHubError) as caught:
            asyncio.run(search.discover_logins(client2, Q, 2))
        self.assertEqual(caught.exception.status, 404,
                         msg="an unrouted URL raises GitHubError 404")
        self.assertTrue(client2.transport is fake2,
                        msg="after the error client.transport is restored")

    def test_D_6(self):
        """D example 6: pages < 1 raises ValueError with no request."""
        seen = []
        fake = make_fake({U1: (load_body("search_page1.json"), H1)}, seen)
        client = GitHubClient(token="x", transport=fake)
        with self.assertRaises(ValueError) as caught:
            asyncio.run(search.discover_logins(client, Q, 0))
        self.assertIsInstance(caught.exception, ValueError,
                              msg="pages=0 raises ValueError")
        self.assertEqual(seen, [], msg="no transport call was made")


if __name__ == "__main__":
    unittest.main()
