"""Tests for megatron.parsers (unittest, offline, real fixtures)."""

import json
import os
import unittest

from megatron.parsers import parse_user_profile, parse_repo_stats

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


class TestParseUserProfile(unittest.TestCase):
    maxDiff = None

    def test_example_1_real_user_torvalds_fixture(self):
        """Example 1: real user_torvalds.json yields the fixture values."""
        data = load_fixture("user_torvalds.json")
        profile = parse_user_profile(data)
        self.assertEqual(profile["login"], "torvalds", msg="login mismatch")
        self.assertEqual(profile["id"], 1024025, msg="id mismatch")
        self.assertEqual(profile["followers"], 325466, msg="followers mismatch")
        self.assertEqual(profile["public_repos"], 12, msg="public_repos mismatch")
        self.assertEqual(profile["name"], "Linus Torvalds", msg="name mismatch")

    def test_example_2_minimal_dict_degrades_to_none_and_zero(self):
        """Example 2 (Tolerant Parser): minimal dict -> None/0 optional keys."""
        profile = parse_user_profile({"login": "x", "id": 1})
        self.assertEqual(profile["followers"], 0, msg="followers must default to 0")
        self.assertEqual(profile["public_repos"], 0, msg="public_repos must default to 0")
        self.assertIsNone(profile["name"], msg="name must default to None")
        self.assertIsNone(profile["company"], msg="company must default to None")
        self.assertIsNone(profile["location"], msg="location must default to None")
        self.assertIsNone(profile["created_at"], msg="created_at must default to None")

    def test_null_optional_fields_become_none(self):
        """Tolerant Parser: explicit null optional fields stay None."""
        data = load_fixture("user_torvalds.json")
        data["name"] = None
        data["company"] = None
        profile = parse_user_profile(data)
        self.assertIsNone(profile["name"], msg="null name must stay None")
        self.assertIsNone(profile["company"], msg="null company must stay None")


class TestParseRepoStats(unittest.TestCase):
    maxDiff = None

    def test_example_3_real_repos_torvalds_fixture(self):
        """Example 3: real repos_torvalds.json gives fixture aggregates."""
        repos = load_fixture("repos_torvalds.json")
        stats = parse_repo_stats("torvalds", repos)
        self.assertEqual(stats["login"], "torvalds", msg="login mismatch")
        self.assertEqual(stats["repo_count"], 12, msg="repo_count mismatch")
        self.assertEqual(stats["non_fork_count"], 9, msg="non_fork_count mismatch")
        self.assertEqual(stats["total_stars"], 262418, msg="total_stars mismatch")
        self.assertEqual(
            stats["languages"], {"C": 8, "OpenSCAD": 1}, msg="languages mismatch"
        )

    def test_empty_repos_list_gives_zero_stats(self):
        """Tolerant Parser: empty repos list degrades to zeroed stats."""
        stats = parse_repo_stats("nobody", [])
        self.assertEqual(stats["repo_count"], 0, msg="repo_count must be 0")
        self.assertEqual(stats["non_fork_count"], 0, msg="non_fork_count must be 0")
        self.assertEqual(stats["total_stars"], 0, msg="total_stars must be 0")
        self.assertEqual(stats["languages"], {}, msg="languages must be empty")

    def test_null_language_is_skipped(self):
        """Tolerant Parser: a null language is skipped, not counted."""
        repos = [{"fork": False, "stargazers_count": 5, "language": None}]
        stats = parse_repo_stats("x", repos)
        self.assertEqual(stats["languages"], {}, msg="null language must be skipped")
        self.assertEqual(stats["total_stars"], 5, msg="stars must still count")


if __name__ == "__main__":
    unittest.main()
