"""Tests for megatron/processors.py.

Does NOT test parsing or storage -- those belong to their own cards' test
modules. Uses inline profile/stats dicts built from the documented torvalds
numbers, never a live network call.
"""

import unittest

from megatron.processors import score_expertise


class TestScoreExpertise(unittest.TestCase):
    maxDiff = None

    def test_example_1_torvalds_score_and_primary_language(self):
        """Example 1: torvalds profile+stats score to 850302 with primary_language "C"."""
        profile = {
            "login": "torvalds",
            "id": 1024025,
            "name": "Linus Torvalds",
            "company": "Linux Foundation",
            "location": "Portland, OR",
            "followers": 325466,
            "public_repos": 12,
            "created_at": "2011-09-03T15:26:22Z",
        }
        stats = {
            "login": "torvalds",
            "repo_count": 12,
            "non_fork_count": 9,
            "total_stars": 262418,
            "languages": {"C": 8, "OpenSCAD": 1},
        }
        record = score_expertise(profile, stats)
        self.assertEqual(record["expertise_score"], 850302, msg="expertise_score should be followers + 2*total_stars")
        self.assertEqual(record["primary_language"], "C", msg="primary_language should be the highest-count language")

    def test_example_2_empty_languages_no_primary(self):
        """Example 2: empty languages and 0 stars give score 7 and primary_language None."""
        profile = {
            "login": "nobody",
            "id": 2,
            "name": None,
            "company": None,
            "location": None,
            "followers": 7,
            "public_repos": 0,
            "created_at": None,
        }
        stats = {
            "login": "nobody",
            "repo_count": 0,
            "non_fork_count": 0,
            "total_stars": 0,
            "languages": {},
        }
        record = score_expertise(profile, stats)
        self.assertEqual(record["expertise_score"], 7, msg="expertise_score should equal followers when total_stars is 0")
        self.assertIsNone(record["primary_language"], msg="primary_language should be None when languages is empty")

    def test_primary_language_tie_broken_lexicographically(self):
        """Behaviour: equal-count languages break the tie by lexicographic order."""
        profile = {
            "login": "tied",
            "id": 3,
            "name": None,
            "company": None,
            "location": None,
            "followers": 0,
            "public_repos": 0,
            "created_at": None,
        }
        stats = {
            "login": "tied",
            "repo_count": 2,
            "non_fork_count": 2,
            "total_stars": 0,
            "languages": {"Zig": 1, "Ada": 1},
        }
        record = score_expertise(profile, stats)
        self.assertEqual(record["primary_language"], "Ada", msg="tie between Zig and Ada should resolve to Ada")

    def test_record_carries_profile_keys_plus_scoring_fields(self):
        """Behaviour: the record is the profile keys extended, not re-serialized."""
        profile = {
            "login": "x",
            "id": 1,
            "name": None,
            "company": None,
            "location": None,
            "followers": 5,
            "public_repos": 0,
            "created_at": None,
        }
        stats = {"login": "x", "repo_count": 0, "non_fork_count": 0, "total_stars": 0, "languages": {}}
        record = score_expertise(profile, stats)
        for key in profile:
            self.assertEqual(record[key], profile[key], msg="record should carry profile key %r unchanged" % key)
        self.assertEqual(
            set(record.keys()) - set(profile.keys()),
            {"total_stars", "languages", "expertise_score", "primary_language"},
            msg="record should add exactly the four scoring fields",
        )


if __name__ == "__main__":
    unittest.main()
