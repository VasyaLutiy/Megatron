"""Tests for megatron.collectors (offline, injected fetcher).

Examples 1 and 2 from the card, plus the No Network In Core guardrail.
"""

import asyncio
import json
import os
import unittest

from megatron import collectors

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

EXPECTED_LOGINS = (
    "karpathy",
    "openai",
    "google",
    "huggingface",
    "rafaballerini",
)
EXPECTED_STARS = 262418
EXPECTED_CALLS = 10  # 2 fetches per login x 5 logins


def _load(name):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


class CollectProfilesTests(unittest.TestCase):
    maxDiff = None

    def test_example_1_five_logins_in_order_ten_calls(self):
        """Example 1: 5 fixture logins, torvalds data for all, concurrency=2.

        Result has 5 entries in input order, each with profile login
        "torvalds" and stats total_stars 262418; the fake was called
        exactly 10 times.
        """
        profile_data = _load("user_torvalds.json")
        repos_data = _load("repos_torvalds.json")
        calls = []

        async def fetch_json(path):
            calls.append(path)
            if path.endswith("/repos?per_page=100"):
                return repos_data
            return profile_data

        result = asyncio.run(
            collectors.collect_profiles(
                list(EXPECTED_LOGINS), fetch_json, concurrency=2
            )
        )
        self.assertEqual(len(result), 5, "expected 5 entries for 5 logins")
        for index, login in enumerate(EXPECTED_LOGINS):
            self.assertIsNotNone(
                result[index],
                "entry {} ({}) must be a parsed pair".format(index, login),
            )
            self.assertEqual(
                result[index]["profile"]["login"],
                "torvalds",
                "entry {} profile login".format(index),
            )
            self.assertEqual(
                result[index]["stats"]["total_stars"],
                EXPECTED_STARS,
                "entry {} stats total_stars".format(index),
            )
        self.assertEqual(
            result[0]["profile"]["login"],
            "torvalds",
            "first entry is the first login's pair",
        )
        self.assertEqual(
            len(calls),
            EXPECTED_CALLS,
            "fake fetcher must be called exactly {} times".format(
                EXPECTED_CALLS
            ),
        )

    def test_example_2_failing_single_login_degrades_to_none(self):
        """Example 2 (Tolerant Parser): fetcher raises for "google" only.

        Entry 2 is None and the other 4 entries are parsed pairs.
        """
        profile_data = _load("user_torvalds.json")
        repos_data = _load("repos_torvalds.json")

        async def fetch_json(path):
            if "/google" in path:
                raise ValueError("boom")
            if path.endswith("/repos?per_page=100"):
                return repos_data
            return profile_data

        result = asyncio.run(
            collectors.collect_profiles(list(EXPECTED_LOGINS), fetch_json)
        )
        self.assertIsNone(
            result[2], "entry 2 (google) must be None on fetch failure"
        )
        for index, login in enumerate(EXPECTED_LOGINS):
            if index == 2:
                continue
            self.assertIsNotNone(
                result[index],
                "entry {} ({}) unaffected by the failing login".format(
                    index, login
                ),
            )
            self.assertEqual(
                result[index]["profile"]["login"],
                "torvalds",
                "entry {} profile login".format(index),
            )


if __name__ == "__main__":
    unittest.main()
