"""Example-based acceptance tests for megatron/collectors.py (card collect).

Independent of megatron/collectors.py's own test suite: this file is the
criterion's author checking the two examples of Function Collect Profiles
from docs/TASK_MEGATRON.md / contour.yaml, one test per example. Never opens
a real network connection -- fetch_json is always a fake coroutine here.
"""

import asyncio
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


def _run(coro):
    """Run a coroutine to completion on a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestCollectProfilesExamples(unittest.TestCase):
    maxDiff = None

    def test_collect_profiles_example_1(self):
        """Collect Profiles example 1: 5 logins, in-order results, fetcher called 10 times."""
        self.assertEqual(
            LOGINS,
            ["karpathy", "openai", "google", "huggingface", "rafaballerini"],
            msg="fixture assumption: search_users_python.json items are these 5 logins in this order",
        )

        calls = []

        async def fetch_json(path):
            calls.append(path)
            if path.startswith("/users/") and path.endswith("/repos?per_page=100"):
                return REPOS_TORVALDS
            return USER_TORVALDS

        results = _run(collect_profiles(LOGINS, fetch_json, concurrency=2))

        self.assertEqual(len(results), 5, msg="example 1: result should have 5 entries, one per login")
        for index, login in enumerate(LOGINS):
            entry = results[index]
            self.assertIsNotNone(entry, msg="example 1: entry for %s should not be None" % login)
            self.assertEqual(
                entry["profile"]["login"], "torvalds",
                msg="example 1: entry %d profile login should be torvalds (from the fake response)" % index,
            )
            self.assertEqual(
                entry["stats"]["total_stars"], 262418,
                msg="example 1: entry %d stats total_stars should be 262418 (from the fake response)" % index,
            )
        self.assertEqual(
            len(calls), 10,
            msg="example 1: fetch_json should be called exactly 10 times (2 calls per login x 5 logins)",
        )

    def test_collect_profiles_example_2_tolerant_parser(self):
        """Collect Profiles example 2 (ref Tolerant Parser): a raise for "google" yields entry 2 as None only."""
        self.assertEqual(LOGINS[2], "google", msg="fixture assumption: third login (index 2) is google")

        async def fetch_json(path):
            if "/users/google" in path:
                raise ValueError("boom")
            if path.endswith("/repos?per_page=100"):
                return REPOS_TORVALDS
            return USER_TORVALDS

        results = _run(collect_profiles(LOGINS, fetch_json, concurrency=2))

        self.assertIsNone(results[2], msg="example 2: entry 2 (google) should be None after fetch_json raised")
        for index in range(5):
            if index == 2:
                continue
            self.assertIsNotNone(
                results[index], msg="example 2: entry %d should still be a parsed pair, unaffected by google's failure" % index,
            )


if __name__ == "__main__":
    unittest.main()
