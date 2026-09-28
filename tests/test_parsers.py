"""Tests for megatron/parsers.py.

Does NOT test collect_profiles, score_expertise or storage -- those belong
to their own cards' test modules. Uses only tests/fixtures/* and inline
minimal dicts, never live network data (Requirement Offline Tests).
"""

import json
import os
import unittest

from megatron.parsers import parse_repo_stats, parse_user_profile

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestParseUserProfile(unittest.TestCase):
    maxDiff = None

    def test_example_1_real_torvalds_fixture(self):
        """Example 1: user_torvalds.json parses to the documented field values."""
        with open(os.path.join(FIXTURES, "user_torvalds.json")) as f:
            data = json.load(f)
        profile = parse_user_profile(data)
        self.assertEqual(profile["login"], "torvalds", msg="login mismatch")
        self.assertEqual(profile["id"], 1024025, msg="id mismatch")
        self.assertEqual(profile["followers"], 325466, msg="followers mismatch")
        self.assertEqual(profile["public_repos"], 12, msg="public_repos mismatch")
        self.assertEqual(profile["name"], "Linus Torvalds", msg="name mismatch")

    def test_example_2_minimal_dict_tolerant_parser(self):
        """Example 2 (ref Tolerant Parser): missing optional keys degrade to None/0."""
        profile = parse_user_profile({"login": "x", "id": 1})
        self.assertEqual(profile["followers"], 0, msg="followers should default to 0")
        self.assertEqual(profile["public_repos"], 0, msg="public_repos should default to 0")
        self.assertIsNone(profile["name"], msg="name should default to None")
        self.assertIsNone(profile["company"], msg="company should default to None")
        self.assertIsNone(profile["location"], msg="location should default to None")
        self.assertIsNone(profile["created_at"], msg="created_at should default to None")


class TestParseRepoStats(unittest.TestCase):
    maxDiff = None

    def test_example_3_real_torvalds_repos_fixture(self):
        """Example 3: repos_torvalds.json (12 repos) aggregates to the documented stats."""
        with open(os.path.join(FIXTURES, "repos_torvalds.json")) as f:
            repos = json.load(f)
        stats = parse_repo_stats("torvalds", repos)
        self.assertEqual(stats["repo_count"], 12, msg="repo_count should count all repos")
        self.assertEqual(stats["non_fork_count"], 9, msg="non_fork_count should exclude forks")
        self.assertEqual(stats["total_stars"], 262418, msg="total_stars should exclude forks")
        self.assertEqual(
            stats["languages"],
            {"C": 8, "OpenSCAD": 1},
            msg="languages should count non-fork repos per language, skipping null",
        )


if __name__ == "__main__":
    unittest.main()
