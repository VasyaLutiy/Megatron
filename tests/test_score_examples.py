"""Example-based acceptance tests for megatron/processors.py (card score).

Independent of megatron/processors.py's own test suite: this file is the
criterion's author checking the two examples of Function Score Expertise
from docs/TASK_MEGATRON.md / contour.yaml, one test per example.
"""

import unittest

from megatron.processors import score_expertise


class TestScoreExpertiseExamples(unittest.TestCase):
    maxDiff = None

    def test_score_expertise_example_1(self):
        """Score Expertise example 1: torvalds-shaped profile/stats give score 850302, primary C."""
        profile = {
            "login": "torvalds",
            "id": 1024025,
            "name": "Linus Torvalds",
            "company": None,
            "location": None,
            "followers": 325466,
            "public_repos": 12,
            "created_at": None,
        }
        stats = {
            "login": "torvalds",
            "repo_count": 12,
            "non_fork_count": 9,
            "total_stars": 262418,
            "languages": {"C": 8, "OpenSCAD": 1},
        }
        record = score_expertise(profile, stats)
        self.assertEqual(
            record["expertise_score"], 850302,
            msg="example 1: expertise_score should be followers + 2*total_stars = 325466 + 2*262418 = 850302",
        )
        self.assertEqual(
            record["primary_language"], "C",
            msg='example 1: primary_language should be "C" (highest language count, 8)',
        )

    def test_score_expertise_example_2(self):
        """Score Expertise example 2: no languages gives primary_language None, score = followers."""
        profile = {
            "login": "minnow",
            "id": 2,
            "name": None,
            "company": None,
            "location": None,
            "followers": 7,
            "public_repos": 0,
            "created_at": None,
        }
        stats = {
            "login": "minnow",
            "repo_count": 0,
            "non_fork_count": 0,
            "total_stars": 0,
            "languages": {},
        }
        record = score_expertise(profile, stats)
        self.assertEqual(
            record["expertise_score"], 7,
            msg="example 2: expertise_score should be followers + 2*total_stars = 7 + 2*0 = 7",
        )
        self.assertIsNone(
            record["primary_language"],
            msg="example 2: primary_language should be None when languages is empty",
        )


if __name__ == "__main__":
    unittest.main()
