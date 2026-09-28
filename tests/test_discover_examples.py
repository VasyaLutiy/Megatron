"""Judge tests for the discover examples O.1, L.1 and R.1.

This file only proves spec examples; it does not test the implementation
internals. All calls go through `search.discover_logins` at call time.
"""

import asyncio
import json
import os
import unittest

from megatron import search
from megatron.github_client import GitHubClient, GitHubError

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

Q = "followers:>5000"
U1 = "https://api.github.com/search/users?q=followers%3A%3E5000&per_page=30"
U2 = "https://api.github.com/search/users?q=followers%3A%3E5000&per_page=30&page=2"


def read_fixture(name):
    # type: (str) -> bytes
    with open(os.path.join(FIXTURES, name), "rb") as handle:
        return handle.read()


def parse_headers_file(name):
    # type: (str) -> dict
    text = read_fixture(name).decode("utf-8")
    lines = text.split("\n")
    headers = {}
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        name_part, _, value_part = line.partition(": ")
        headers[name_part] = value_part
    return headers


def load_logins(name):
    # type: (str) -> list
    data = json.loads(read_fixture(name).decode("utf-8"))
    return [item["login"] for item in data["items"]]


L1 = load_logins("search_page1.json")
L2 = load_logins("search_page2.json")


def make_fake(routes, seen):
    # type: (dict, list) -> object
    def fake(url, headers):
        # type: (str, dict) -> tuple
        seen.append(url)
        if url in routes:
            status, resp_headers, body = routes[url]
            return status, dict(resp_headers), body
        return 404, {}, b'{"message": "Not Found"}'

    return fake


def route_page1(headers=None):
    # type: (object) -> tuple
    return (
        200,
        parse_headers_file("search_page1.headers.txt")
        if headers is None
        else headers,
        read_fixture("search_page1.json"),
    )


def route_page2():
    # type: () -> tuple
    return (
        200,
        parse_headers_file("search_page2.headers.txt"),
        read_fixture("search_page2.json"),
    )


class DiscoverExamples(unittest.TestCase):
    maxDiff = None

    def test_O_1_order_over_two_pages(self):
        """O example 1: logins are L1 + L2 in API order across two pages."""
        seen = []  # type: list
        routes = {U1: route_page1(), U2: route_page2()}
        fake = make_fake(routes, seen)
        client = GitHubClient(token="x", transport=fake)
        result = asyncio.run(search.discover_logins(client, Q, 2))
        self.assertEqual(result["logins"], L1 + L2, msg="logins in API order")
        self.assertEqual(len(result["logins"]), 60, msg="60 logins")
        self.assertEqual(
            result["logins"][29:31],
            ["geohot", "mattpocock"],
            msg="page seam: last of page 1 followed by first of page 2",
        )
        self.assertEqual(seen, [U1, U2], msg="urls seen")
        self.assertEqual(result["total_count"], 1230, msg="total_count")
        self.assertEqual(result["pages"], 2, msg="pages")
        self.assertIs(client.transport, fake, msg="transport restored")

    def test_L_1_link_header_is_the_only_pager(self):
        """L example 1: no link header on page 1 means only page 1."""
        seen = []  # type: list
        headers = parse_headers_file("search_page1.headers.txt")
        for key in list(headers):
            if key.lower() == "link":
                del headers[key]
        routes = {U1: route_page1(headers), U2: route_page2()}
        fake = make_fake(routes, seen)
        client = GitHubClient(token="x", transport=fake)
        result = asyncio.run(search.discover_logins(client, Q, 2))
        self.assertEqual(result["logins"], L1, msg="only page 1 logins")
        self.assertEqual(result["pages"], 1, msg="pages")
        self.assertEqual(seen, [U1], msg="page 2 never requested")

    def test_R_1_search_rate_limit_waits_through_client(self):
        """R example 1: remaining 0 on page 1 forces one 60 s sleep."""
        seen = []  # type: list
        sleeps = []  # type: list

        async def rec(seconds):
            # type: (float) -> None
            sleeps.append((seconds, len(seen)))

        headers = parse_headers_file("search_page1.headers.txt")
        for key in list(headers):
            if key.lower() == "x-ratelimit-remaining":
                headers[key] = "0"
        routes = {U1: route_page1(headers), U2: route_page2()}
        fake = make_fake(routes, seen)
        client = GitHubClient(
            token="x", transport=fake, sleep=rec, clock=lambda: 1790599575
        )
        result = asyncio.run(search.discover_logins(client, Q, 2))
        self.assertEqual(
            sleeps, [(60, 1)], msg="one sleep of 60 s after the first request"
        )
        self.assertEqual(
            client.rate_limit,
            {"limit": 10, "remaining": 8, "reset": 1790599635},
            msg="rate limit state from page 2",
        )
        self.assertEqual(result["pages"], 2, msg="both pages fetched")


if __name__ == "__main__":
    unittest.main()
