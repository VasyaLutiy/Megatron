"""Tests for the GitHubError status boundary — spec section 3, example S.1.

The only pre-existing error test uses status 404, so a client that
raises only for status > 400 passes the whole suite. This file sits on
the boundary: status 400 must raise GitHubError too.

Every test runs offline: the transport is a fake recording each url,
never a socket.
"""

import asyncio
import unittest

from megatron import github_client

USER_URL = "https://api.github.com/users/torvalds"


class TestStatusBoundary(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_s_example_1(self):
        """S example 1: status 400 raises GitHubError with .status == 400."""
        calls = []

        def transport(url, headers):
            # type: (str, dict) -> tuple
            calls.append(url)
            return (400, {}, b'{"message": "Not Found"}')

        client = github_client.GitHubClient(token="x", transport=transport)
        with self.assertRaises(
                github_client.GitHubError,
                msg="status 400 (the >= 400 boundary) raises GitHubError") as ctx:
            asyncio.run(client.fetch_json("/users/torvalds"))
        self.assertEqual(
            ctx.exception.status, 400,
            msg="GitHubError.status is the boundary value 400")
        self.assertEqual(
            calls, [USER_URL],
            msg="the transport was called exactly once, for the user URL")
