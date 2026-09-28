"""Tests for megatron.github_client — spec section 3, examples A.1-A.8.

Every test runs offline: the transport is a fake keyed by URL serving
fixture bodies; urllib_transport is only identity-checked, never called.
"""

import asyncio
import json
import os
import unittest
from unittest.mock import patch

from megatron import github_client
from megatron.github_client import (
    API_ROOT,
    GitHubClient,
    GitHubError,
    parse_next_link,
    urllib_transport,
)
from megatron.parsers import parse_repo_stats

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

REPO_PAGE_URL = API_ROOT + "/users/torvalds/repos?per_page=5"
PAGE2_URL = "https://api.github.com/user/1024025/repos?per_page=5&page=2"
PAGE3_URL = "https://api.github.com/user/1024025/repos?per_page=5&page=3"
USER_URL = API_ROOT + "/users/torvalds"


def fixture_bytes(name):
    # type: (str) -> bytes
    with open(os.path.join(FIXTURES, name), "rb") as handle:
        return handle.read()


def parse_headers_file(name):
    # type: (str) -> dict
    """Parse a .headers.txt fixture: skip the status line, split at ': '."""
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    headers = {}
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        name_part, _, value = line.partition(": ")
        headers[name_part] = value
    return headers


def fake_transport(routes):
    # type: (dict) -> object
    """A transport recording (url, headers) per call, serving from routes."""
    calls = []

    def transport(url, headers):
        # type: (str, dict) -> tuple
        calls.append((url, headers))
        status, resp_headers, body = routes[url]
        return status, dict(resp_headers), body

    transport.calls = calls
    return transport


class TestParseNextLink(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_a_example_1(self):
        """A example 1: parse_next_link of the three page fixtures."""
        page1 = parse_headers_file("repos_torvalds_page1.headers.txt")
        page2 = parse_headers_file("repos_torvalds_page2.headers.txt")
        page3 = parse_headers_file("repos_torvalds_page3.headers.txt")
        self.assertEqual(
            parse_next_link(page1["link"]), PAGE2_URL,
            msg="page 1 link rel=next must be the page 2 URL")
        self.assertEqual(
            parse_next_link(page2["link"]), PAGE3_URL,
            msg="page 2 link rel=next must be the page 3 URL")
        self.assertIsNone(
            parse_next_link(page3["link"]),
            msg="page 3 link has no rel=next, so None")
        self.assertIsNone(parse_next_link(""), msg="empty header gives None")
        self.assertIsNone(parse_next_link(None), msg="None gives None")


class TestFetchJson(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_a_example_2(self):
        """A example 2: paginated repos fetched across 3 pages in order."""
        routes = {
            REPO_PAGE_URL: (200, parse_headers_file(
                "repos_torvalds_page1.headers.txt"),
                fixture_bytes("repos_torvalds_page1.json")),
            PAGE2_URL: (200, parse_headers_file(
                "repos_torvalds_page2.headers.txt"),
                fixture_bytes("repos_torvalds_page2.json")),
            PAGE3_URL: (200, parse_headers_file(
                "repos_torvalds_page3.headers.txt"),
                fixture_bytes("repos_torvalds_page3.json")),
        }
        transport = fake_transport(routes)
        client = GitHubClient(token="x", transport=transport)
        result = asyncio.run(client.fetch_json("/users/torvalds/repos?per_page=5"))
        self.assertEqual(
            [call[0] for call in transport.calls],
            [REPO_PAGE_URL, PAGE2_URL, PAGE3_URL],
            msg="the transport saw exactly the 3 page URLs in order")
        self.assertEqual(len(result), 12, msg="12 repo items across 3 pages")
        self.assertIsInstance(result, list, msg="a list body is concatenated")
        stats = parse_repo_stats("torvalds", result)
        self.assertEqual(
            stats,
            {
                "login": "torvalds",
                "repo_count": 12,
                "non_fork_count": 9,
                "total_stars": 262425,
                "languages": stats["languages"],
            },
            msg="repo stats over the concatenated pages")

    def test_a_example_3(self):
        """A example 3: a dict body is returned as is; rate limit recorded."""
        routes = {
            USER_URL: (200, parse_headers_file("rate_limit_headers.txt"),
                       fixture_bytes("user_torvalds.json")),
        }
        transport = fake_transport(routes)
        client = GitHubClient(token="x", transport=transport)
        result = asyncio.run(client.fetch_json("/users/torvalds"))
        self.assertEqual(result["login"], "torvalds", msg="login of the fixture")
        self.assertEqual(len(transport.calls), 1, msg="exactly one call")
        self.assertEqual(
            client.rate_limit,
            {"limit": 60, "remaining": 59, "reset": 1790594886},
            msg="rate limit parsed from the response headers")

    def test_a_example_4(self):
        """A example 4: Authorization from token or GITHUB_TOKEN."""
        routes = {
            USER_URL: (200, {}, fixture_bytes("user_torvalds.json")),
        }
        transport = fake_transport(routes)
        client = GitHubClient(token="t0k", transport=transport)
        asyncio.run(client.fetch_json("/users/torvalds"))
        self.assertEqual(
            transport.calls[0][1].get("Authorization"), "Bearer t0k",
            msg="truthy token sends Bearer t0k")

        transport2 = fake_transport(routes)
        with patch.dict(os.environ, {"GITHUB_TOKEN": "envtok"}):
            client2 = GitHubClient(token=None, transport=transport2)
        asyncio.run(client2.fetch_json("/users/torvalds"))
        self.assertEqual(
            transport2.calls[0][1].get("Authorization"), "Bearer envtok",
            msg="GITHUB_TOKEN read at construction sends Bearer envtok")

        transport3 = fake_transport(routes)
        with patch.dict(os.environ, {}, clear=True):
            client3 = GitHubClient(token=None, transport=transport3)
        asyncio.run(client3.fetch_json("/users/torvalds"))
        self.assertNotIn(
            "Authorization", transport3.calls[0][1],
            msg="no token, no Authorization header")
        self.assertEqual(
            transport3.calls[0][1].get("Accept"),
            "application/vnd.github+json",
            msg="Accept always sent")
        self.assertEqual(
            transport3.calls[0][1].get("User-Agent"), "megatron",
            msg="User-Agent always sent")

    def test_a_example_5(self):
        """A example 5: sleeps exactly the reset wait on the second request."""
        headers = parse_headers_file("rate_limit_headers.txt")
        headers["x-ratelimit-remaining"] = "0"
        routes = {USER_URL: (200, headers, fixture_bytes("user_torvalds.json"))}
        transport = fake_transport(routes)
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        client = GitHubClient(
            token="x", transport=transport, sleep=fake_sleep,
            clock=lambda: 1790594766)
        asyncio.run(client.fetch_json("/users/torvalds"))
        self.assertEqual(sleeps, [], msg="first request does not sleep")
        asyncio.run(client.fetch_json("/users/torvalds"))
        self.assertEqual(sleeps, [120], msg="sleeps exactly 120 seconds")
        self.assertEqual(len(transport.calls), 2, msg="two requests made")

    def test_a_example_6(self):
        """A example 6: status 404 raises GitHubError with .status 404."""
        routes = {
            USER_URL: (404, {}, b'{"message": "Not Found"}'),
        }
        transport = fake_transport(routes)
        client = GitHubClient(token="x", transport=transport)
        with self.assertRaises(GitHubError, msg="404 raises GitHubError") as ctx:
            asyncio.run(client.fetch_json("/users/torvalds"))
        self.assertEqual(ctx.exception.status, 404, msg="GitHubError.status")

    def test_a_example_7(self):
        """A example 7: max_pages=2 stops the 3-page chain after 2 pages."""
        routes = {
            REPO_PAGE_URL: (200, parse_headers_file(
                "repos_torvalds_page1.headers.txt"),
                fixture_bytes("repos_torvalds_page1.json")),
            PAGE2_URL: (200, parse_headers_file(
                "repos_torvalds_page2.headers.txt"),
                fixture_bytes("repos_torvalds_page2.json")),
            PAGE3_URL: (200, parse_headers_file(
                "repos_torvalds_page3.headers.txt"),
                fixture_bytes("repos_torvalds_page3.json")),
        }
        transport = fake_transport(routes)
        client = GitHubClient(token="x", transport=transport, max_pages=2)
        result = asyncio.run(client.fetch_json("/users/torvalds/repos?per_page=5"))
        self.assertEqual(len(result), 10, msg="10 items from 2 pages of 5")
        self.assertEqual(len(transport.calls), 2, msg="exactly 2 transport calls")


class TestDefaults(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_a_example_8(self):
        """A example 8: the default transport is the module urllib_transport."""
        with patch.dict(os.environ, {}, clear=True):
            client = GitHubClient()
        self.assertIs(
            client.transport, urllib_transport,
            msg="GitHubClient() with nothing patched uses urllib_transport")
        self.assertIs(
            client.transport, github_client.urllib_transport,
            msg="the looked-up module global is the same callable")
