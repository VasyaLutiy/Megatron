"""Tests for megatron/collectors.py.

Does NOT test parse_user_profile/parse_repo_stats correctness in depth
(that is tests/test_parsers.py) and never opens a real network connection
-- fetch_json is always a fake coroutine here (Requirement Offline Tests).
"""

import json
import os
import unittest

from megatron.collectors import collect_profiles

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

with open(os.path.join(FIXTURES, "search_users_python.json")) as _f:
    LOGINS = [item["login"] for item in json.load(_f)["items"]]

with open(os.path.join(FIXTURES, "user_torvalds.json")) as _f:
    USER_TORVALDS = json.load(_f)

with open(os.path.join(FIXTURES, "repos_torvalds.json")) as _f:
    REPOS_TORVALDS = json.load(_f)


class TestCollectProfiles(unittest.TestCase):
    maxDiff = None

    def test_example_1_all_succeed_in_order_with_call_count(self):
        """Example 1: 5 logins collect in input order with the fake called 10 times."""
        calls = []

        async def fetch_json(path):
            calls.append(path)
            if "/repos" in path:
                return REPOS_TORVALDS
            return USER_TORVALDS

        results = asyncio_run(collect_profiles(LOGINS, fetch_json, concurrency=2))

        self.assertEqual(len(results), 5, msg="collect_profiles should return one entry per login")
        self.assertEqual(len(calls), 10, msg="fetch_json should be called exactly twice per login (10 total)")
        for entry in results:
            self.assertIsNotNone(entry, msg="every entry should succeed when fetch_json never raises")
            self.assertEqual(entry["profile"]["login"], "torvalds", msg="profile login should come from the fake response")
            self.assertEqual(entry["stats"]["total_stars"], 262418, msg="stats total_stars should come from the fake repos response")

    def test_example_2_one_failure_yields_none_entry_others_unaffected(self):
        """Example 2 (ref Tolerant Parser): a raise for "google" gives entry 2 as None only."""

        async def fetch_json(path):
            if "/google" in path:
                raise ValueError("boom")
            if "/repos" in path:
                return REPOS_TORVALDS
            return USER_TORVALDS

        results = asyncio_run(collect_profiles(LOGINS, fetch_json, concurrency=2))

        self.assertEqual(LOGINS[2], "google", msg="fixture assumption: third login is google")
        self.assertIsNone(results[2], msg="the failing login's entry should be None")
        for index, entry in enumerate(results):
            if index == 2:
                continue
            self.assertIsNotNone(entry, msg="login at index %d should still succeed" % index)
            self.assertEqual(entry["profile"]["login"], "torvalds", msg="unaffected entries should still parse correctly")


def asyncio_run(coro):
    """Run a coroutine to completion (local shim, avoids depending on asyncio.run version quirks)."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


if __name__ == "__main__":
    unittest.main()
