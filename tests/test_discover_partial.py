"""Examples P.2-P.5 of docs/TASK_MEGATRON_V6.md for megatron.search."""

import asyncio
import json
import unittest

from megatron import search
from megatron.github_client import GitHubClient, GitHubError

Q = "followers:>5000"
U1 = "https://api.github.com/search/users?q=followers%3A%3E5000&per_page=30"


def page_body(page):
    # type: (int) -> bytes
    data = {
        "total_count": 240,
        "incomplete_results": False,
        "items": [{"login": "p%d_u%02d" % (page, i)} for i in range(30)],
    }
    return json.dumps(data).encode("utf-8")


def make_walk_fake(fail_on=None):
    # type: (object) -> tuple
    calls = []

    def fake(url, headers):
        # type: (str, dict) -> tuple
        calls.append(url)
        if fail_on is not None and len(calls) == fail_on:
            raise GitHubError("HTTP 403 for " + url, 403)
        if url == U1:
            page = 1
        else:
            page = int(url.split("&page=")[1])
        link = '<' + U1 + '&page=%d>; rel="next"' % (page + 1)
        return 200, {"Link": link}, page_body(page)

    return fake, calls


def walk_logins(last_page):
    # type: (int) -> list
    return ["p%d_u%02d" % (page, i)
            for page in range(1, last_page + 1) for i in range(30)]


def make_runtime_error_fake():
    # type: () -> tuple
    calls = []

    def fake(url, headers):
        # type: (str, dict) -> tuple
        calls.append(url)
        if len(calls) >= 2:
            raise RuntimeError("transport blew up on " + url)
        link = '<' + U1 + '&page=2>; rel="next"'
        return 200, {"Link": link}, page_body(1)

    return fake, calls


class TestDiscoverPartial(unittest.TestCase):
    maxDiff = None

    def test_P_2(self):
        """P example 2: failure on call 6 keeps the 150 logins of pages 1-5."""
        fake, calls = make_walk_fake(fail_on=6)
        client = GitHubClient(token="x", transport=fake)
        result = asyncio.run(search.discover_logins(client, Q, 8))
        self.assertEqual(
            result,
            {"logins": walk_logins(5), "total_count": 240,
             "incomplete_results": False, "pages": 5,
             "failed_page": 6, "failed_status": 403},
            msg="a failure on page 6 keeps pages 1-5 and names the failure")
        self.assertEqual(len(result["logins"]), 150,
                         msg="five pages give 150 logins")
        self.assertEqual(result["logins"][0], "p1_u00",
                         msg="the first login is p1_u00")
        self.assertEqual(result["logins"][-1], "p5_u29",
                         msg="the last login is p5_u29")
        self.assertEqual(len(calls), 6,
                         msg="exactly 6 transport calls were made")
        self.assertTrue(client.transport is fake,
                        msg="the transport is restored after the failure")

    def test_P_3(self):
        """P example 3: failure on call 1 gives an empty partial result."""
        fake, calls = make_walk_fake(fail_on=1)
        client = GitHubClient(token="x", transport=fake)
        result = asyncio.run(search.discover_logins(client, Q, 4))
        self.assertEqual(
            result,
            {"logins": [], "total_count": None,
             "incomplete_results": False, "pages": 0,
             "failed_page": 1, "failed_status": 403},
            msg="a failure on page 1 gives no logins and total_count None")
        self.assertEqual(len(calls), 1,
                         msg="only the first transport call was made")
        self.assertTrue(client.transport is fake,
                        msg="the transport is restored after the failure")

    def test_P_4(self):
        """P example 4: a transport raising RuntimeError propagates."""
        fake, calls = make_runtime_error_fake()
        client = GitHubClient(token="x", transport=fake)
        with self.assertRaises(RuntimeError) as caught:
            asyncio.run(search.discover_logins(client, Q, 3))
        self.assertIsInstance(caught.exception, RuntimeError,
                              msg="RuntimeError propagates out of "
                                  "discover_logins")
        self.assertEqual(len(calls), 2,
                         msg="the transport was called twice before the "
                             "propagation")
        self.assertTrue(client.transport is fake,
                        msg="the transport is restored after RuntimeError")

    def test_P_5(self):
        """P example 5: a clean walk of 3 pages keeps exactly four keys."""
        fake, calls = make_walk_fake()
        client = GitHubClient(token="x", transport=fake)
        result = asyncio.run(search.discover_logins(client, Q, 3))
        self.assertEqual(
            result,
            {"logins": walk_logins(3), "total_count": 240,
             "incomplete_results": False, "pages": 3},
            msg="a clean walk returns exactly the four original keys")
        self.assertNotIn("failed_page", result,
                         msg="no failed_page key on full success")
        self.assertNotIn("failed_status", result,
                         msg="no failed_status key on full success")
        self.assertEqual(len(result["logins"]), 90,
                         msg="three pages give 90 logins")
        self.assertEqual(len(calls), 3,
                         msg="exactly 3 transport calls were made")


if __name__ == "__main__":
    unittest.main()
