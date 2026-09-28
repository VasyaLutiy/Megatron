"""Example-based acceptance tests for megatron/parsers.py (card parsers).

Independent of megatron/parsers.py's own test suite: this file is the
criterion's author checking the three examples of Function Parse Profile
Data from docs/TASK_MEGATRON.md / contour.yaml, one test per example.
"""

import json
import os
import unittest

from megatron.parsers import parse_repo_stats, parse_user_profile

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestParseProfileDataExamples(unittest.TestCase):
    maxDiff = None

    def test_parse_user_profile_example_1(self):
        """Parse Profile Data example 1: real user_torvalds.json fixture fields."""
        with open(os.path.join(FIXTURES, "user_torvalds.json")) as f:
            data = json.load(f)
        profile = parse_user_profile(data)
        self.assertEqual(profile["login"], "torvalds", msg="example 1: login should be torvalds")
        self.assertEqual(profile["id"], 1024025, msg="example 1: id should be 1024025")
        self.assertEqual(profile["followers"], 325466, msg="example 1: followers should be 325466")
        self.assertEqual(profile["public_repos"], 12, msg="example 1: public_repos should be 12")
        self.assertEqual(profile["name"], "Linus Torvalds", msg="example 1: name should be Linus Torvalds")

    def test_parse_user_profile_example_2_tolerant_parser(self):
        """Parse Profile Data example 2 (ref Tolerant Parser): minimal dict degrades to None/0."""
        profile = parse_user_profile({"login": "x", "id": 1})
        self.assertEqual(profile["followers"], 0, msg="example 2: missing followers should default to 0")
        self.assertEqual(profile["public_repos"], 0, msg="example 2: missing public_repos should default to 0")
        self.assertIsNone(profile["name"], msg="example 2: missing name should default to None")
        self.assertIsNone(profile["company"], msg="example 2: missing company should default to None")
        self.assertIsNone(profile["location"], msg="example 2: missing location should default to None")
        self.assertIsNone(profile["created_at"], msg="example 2: missing created_at should default to None")

    def test_parse_repo_stats_example_3(self):
        """Parse Profile Data example 3: real repos_torvalds.json fixture (12 repos)."""
        with open(os.path.join(FIXTURES, "repos_torvalds.json")) as f:
            repos = json.load(f)
        stats = parse_repo_stats("torvalds", repos)
        self.assertEqual(stats["repo_count"], 12, msg="example 3: repo_count should be 12")
        self.assertEqual(stats["non_fork_count"], 9, msg="example 3: non_fork_count should be 9")
        self.assertEqual(stats["total_stars"], 262418, msg="example 3: total_stars should be 262418")
        self.assertEqual(
            stats["languages"], {"C": 8, "OpenSCAD": 1},
            msg='example 3: languages should be {"C": 8, "OpenSCAD": 1}',
        )


if __name__ == "__main__":
    unittest.main()
