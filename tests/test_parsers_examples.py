"""Example-based tests for megatron/parsers.py.

Criterion: the examples in docs/TASK_MEGATRON.md / contour.yaml for
Parse Profile Data. One test per example, offline, stdlib only.
"""

import json
import os
import unittest

from megatron.parsers import parse_user_profile, parse_repo_stats

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name):
    with open(os.path.join(FIXTURE_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


class TestParseProfileData(unittest.TestCase):
    maxDiff = None

    def test_example_1_user_torvalds_fixture(self):
        """Parse Profile Data example 1: real user_torvalds.json fixture."""
        data = _load_fixture("user_torvalds.json")
        profile = parse_user_profile(data)
        self.assertEqual(profile["login"], "torvalds", msg="login must be torvalds")
        self.assertEqual(profile["id"], 1024025, msg="id must be 1024025")
        self.assertEqual(profile["followers"], 325466, msg="followers must be 325466")
        self.assertEqual(
            profile["public_repos"], 12, msg="public_repos must be 12"
        )
        self.assertEqual(
            profile["name"], "Linus Torvalds", msg='name must be "Linus Torvalds"'
        )

    def test_example_2_minimal_dict_missing_fields(self):
        """Parse Profile Data example 2: minimal dict, optional keys degrade (Tolerant Parser)."""
        profile = parse_user_profile({"login": "x", "id": 1})
        self.assertEqual(profile["followers"], 0, msg="missing followers must be 0")
        self.assertEqual(
            profile["public_repos"], 0, msg="missing public_repos must be 0"
        )
        self.assertIsNone(profile["name"], msg="missing name must be None")
        self.assertIsNone(profile["company"], msg="missing company must be None")
        self.assertIsNone(profile["location"], msg="missing location must be None")
        self.assertIsNone(profile["created_at"], msg="missing created_at must be None")

    def test_example_3_repos_torvalds_fixture(self):
        """Parse Profile Data example 3: real repos_torvalds.json fixture (12 repos)."""
        repos = _load_fixture("repos_torvalds.json")
        stats = parse_repo_stats("torvalds", repos)
        self.assertEqual(stats["repo_count"], 12, msg="repo_count must be 12")
        self.assertEqual(stats["non_fork_count"], 9, msg="non_fork_count must be 9")
        self.assertEqual(stats["total_stars"], 262418, msg="total_stars must be 262418")
        self.assertEqual(
            stats["languages"],
            {"C": 8, "OpenSCAD": 1},
            msg="languages must be {'C': 8, 'OpenSCAD': 1}",
        )


if __name__ == "__main__":
    unittest.main()
