"""Tests for megatron.processors.score_expertise (one test per example)."""

import unittest

from megatron.processors import score_expertise

TORVALDS_PROFILE = {
    "login": "torvalds",
    "id": 1024025,
    "name": "Linus Torvalds",
    "company": None,
    "location": "Portland, OR",
    "followers": 325466,
    "public_repos": 12,
    "created_at": "2011-09-07T15:26:32Z",
}

TORVALDS_STATS = {
    "login": "torvalds",
    "repo_count": 12,
    "non_fork_count": 9,
    "total_stars": 262418,
    "languages": {"C": 8, "OpenSCAD": 1},
}


class TestScoreExpertise(unittest.TestCase):

    maxDiff = None

    def test_example_1_torvalds_score_and_primary_language(self):
        """Example 1: torvalds profile + stats -> score 1635, primary 'C'."""
        record = score_expertise(TORVALDS_PROFILE, TORVALDS_STATS)
        self.assertEqual(record["expertise_score"], 1635,
                         msg="expertise_score must be round(100*log10(325466+1) + 200*log10(262418+1)) = 1635")
        self.assertEqual(record["primary_language"], "C",
                         msg="primary_language must be the language with the highest count")

    def test_example_2_empty_languages_gives_none_and_score_from_followers(self):
        """Example 2: empty languages, total_stars 0, followers 7 -> 90, None."""
        profile = dict(TORVALDS_PROFILE)
        profile["followers"] = 7
        stats = {
            "login": "x",
            "repo_count": 0,
            "non_fork_count": 0,
            "total_stars": 0,
            "languages": {},
        }
        record = score_expertise(profile, stats)
        self.assertEqual(record["expertise_score"], 90,
                         msg="score must be round(100*log10(7+1) + 200*log10(0+1)) = 90")
        self.assertIsNone(record["primary_language"],
                          msg="primary_language must be None when languages is empty")

    def test_record_carries_profile_keys_plus_scoring_fields(self):
        """Rule: Expert Record = Expert Profile keys plus total_stars,
        languages, expertise_score, primary_language (no second serialization)."""
        record = score_expertise(TORVALDS_PROFILE, TORVALDS_STATS)
        expected = dict(TORVALDS_PROFILE)
        expected["total_stars"] = 262418
        expected["languages"] = {"C": 8, "OpenSCAD": 1}
        expected["expertise_score"] = 1635
        expected["primary_language"] = "C"
        self.assertEqual(record, expected,
                         msg="record must be the profile keys plus the four scoring fields")

    def test_profile_dict_is_not_mutated(self):
        """Rule: no second serialization / mutation of the input profile."""
        before = dict(TORVALDS_PROFILE)
        score_expertise(TORVALDS_PROFILE, TORVALDS_STATS)
        self.assertEqual(TORVALDS_PROFILE, before,
                         msg="input profile must stay unchanged")

    def test_tie_broken_by_lexicographic_order(self):
        """Rule: equal counts are broken by lexicographic order of the name."""
        stats = {
            "login": "t",
            "repo_count": 2,
            "non_fork_count": 2,
            "total_stars": 0,
            "languages": {"zig": 2, "ada": 2},
        }
        profile = dict(TORVALDS_PROFILE)
        profile["followers"] = 0
        record = score_expertise(profile, stats)
        self.assertEqual(record["primary_language"], "ada",
                         msg="tie must resolve to the lexicographically first language")


if __name__ == "__main__":
    unittest.main()
