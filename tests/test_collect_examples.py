"""Example-based tests for megatron.collectors.Collect Profiles.

Examples taken from contour.yaml / docs/TASK_MEGATRON.md. Offline only:
all GitHub data comes from tests/fixtures/*. Stdlib only, Python 3.9.
"""

import asyncio
import json
import os
import unittest

from megatron.collectors import collect_profiles

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load(name):
    with open(os.path.join(FIXTURE_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


def _fixture_logins():
    return [item["login"] for item in _load("search_users_python.json")["items"]]


class CollectProfilesExamples(unittest.TestCase):
    maxDiff = None

    def test_example_1_collect_profiles_order_and_call_count(self):
        """Collect Profiles example 1: 5 fixture logins, fake fetcher
        returning torvalds fixtures; result has 5 entries in input order,
        each with profile login "torvalds" and stats total_stars 262418,
        and the fake was called exactly 10 times."""
        logins = _fixture_logins()
        self.assertEqual(
            logins,
            ["karpathy", "openai", "google", "huggingface", "rafaballerini"],
            msg="fixture search_users_python.json should supply the 5 example logins",
        )
        profile_data = _load("user_torvalds.json")
        repos_data = _load("repos_torvalds.json")
        calls = []

        async def fetch_json(path):
            calls.append(path)
            if path.endswith("/repos?per_page=100"):
                return repos_data
            return profile_data

        result = asyncio.run(
            collect_profiles(logins, fetch_json, concurrency=2)
        )

        self.assertEqual(len(result), 5, msg="result must have 5 entries")
        self.assertEqual(
            [entry["profile"]["login"] for entry in result],
            ["torvalds"] * 5,
            msg="every entry's profile login must be 'torvalds'",
        )
        self.assertEqual(
            [entry["stats"]["total_stars"] for entry in result],
            [262418] * 5,
            msg="every entry's stats total_stars must be 262418",
        )
        self.assertEqual(len(calls), 10, msg="fetcher must be called exactly 10 times")

    def test_example_2_single_login_failure_yields_none(self):
        """Collect Profiles example 2: same 5 logins, fetcher raises
        ValueError for "google" only; entry 2 is None and the other 4
        entries are parsed pairs (Tolerant Parser)."""
        logins = _fixture_logins()
        profile_data = _load("user_torvalds.json")
        repos_data = _load("repos_torvalds.json")

        async def fetch_json(path):
            if "/google/" in path:
                raise ValueError("google is unreachable")
            if path.endswith("/repos?per_page=100"):
                return repos_data
            return profile_data

        result = asyncio.run(collect_profiles(logins, fetch_json))

        self.assertIsNone(result[2], msg="entry 2 (google) must be None")
        self.assertEqual(
            len(result), 5, msg="result must still have 5 entries"
        )
        for i, login in enumerate(logins):
            if i == 2:
                continue
            self.assertIsNotNone(
                result[i],
                msg="entry {} ({}) must be a parsed pair, not None".format(i, login),
            )
            self.assertEqual(
                result[i]["profile"]["login"],
                "torvalds",
                msg="entry {} profile login must be 'torvalds'".format(i),
            )
            self.assertIn(
                "stats",
                result[i],
                msg="entry {} must contain a stats dict".format(i),
            )


if __name__ == "__main__":
    unittest.main()
