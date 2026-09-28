"""Example-based tests for megatron/processors.score_expertise.

One test per numbered example of the Function `Score Expertise` as given in
docs/TASK_MEGATRON.md and contour.yaml. All values are read from the real
fixtures (tests/fixtures/user_torvalds.json, repos_torvalds.json,
fetched 2026-09-28); no invented numbers.
"""

import json
import os
import unittest

from megatron.processors import score_expertise

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
USER_JSON = os.path.join(FIXTURES, "user_torvalds.json")
REPOS_JSON = os.path.join(FIXTURES, "repos_torvalds.json")

maxDiff = None


def load_json(path):
    # type: (str) -> object
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def torvalds_profile():
    # type: () -> dict
    """Expert Profile values read from the real user_torvalds.json fixture."""
    data = load_json(USER_JSON)
    return {
        "login": data["login"],
        "id": data["id"],
        "name": data.get("name"),
        "company": data.get("company"),
        "location": data.get("location"),
        "followers": data["followers"],
        "public_repos": data["public_repos"],
        "created_at": data.get("created_at"),
    }


def torvalds_stats():
    # type: () -> dict
    """Repo Stats values from the real repos_torvalds.json fixture
    (12 repos, 3 forks, languages counted over non-fork repos)."""
    repos = load_json(REPOS_JSON)
    languages = {}
    total_stars = 0
    for repo in repos:
        if repo.get("fork"):
            continue
        total_stars += repo.get("stargazers_count", 0)
        lang = repo.get("language")
        if lang is not None:
            languages[lang] = languages.get(lang, 0) + 1
    return {
        "login": "torvalds",
        "repo_count": len(repos),
        "non_fork_count": sum(1 for r in repos if not r.get("fork")),
        "total_stars": total_stars,
        "languages": languages,
    }


class TestScoreExpertiseExamples(unittest.TestCase):
    def test_example_1_torvalds_score_and_primary_language(self):
        """Score Expertise example 1: torvalds profile (followers 325466) and
        stats (total_stars 262418, languages {"C": 8, "OpenSCAD": 1}) ->
        expertise_score 1635, primary_language "C"."""
        profile = torvalds_profile()
        stats = torvalds_stats()
        self.assertEqual(profile["followers"], 325466,
                         msg="fixture profile followers must be 325466")
        self.assertEqual(stats["total_stars"], 262418,
                         msg="fixture stats total_stars must be 262418")
        self.assertEqual(stats["languages"], {"C": 8, "OpenSCAD": 1},
                         msg="fixture stats languages must be {'C': 8, 'OpenSCAD': 1}")
        record = score_expertise(profile, stats)
        self.assertEqual(record["expertise_score"], 1635,
                         msg="expertise_score must be round(100*log10(325466+1) + 200*log10(262418+1)) = 1635")
        self.assertEqual(record["primary_language"], "C",
                         msg="primary_language must be 'C' (count 8 > OpenSCAD 1)")

    def test_example_1_record_carries_profile_keys_plus_scoring_fields(self):
        """Score Expertise example 1 (record shape): the record carries the
        Expert Profile keys plus total_stars, languages, expertise_score,
        primary_language, and the profile is not serialized a second time
        (its own values are unchanged)."""
        profile = torvalds_profile()
        stats = torvalds_stats()
        record = score_expertise(profile, stats)
        for key in ("login", "id", "name", "company", "location",
                    "followers", "public_repos", "created_at"):
            self.assertIn(key, record,
                          msg="record must carry Expert Profile key %r" % key)
            self.assertEqual(record[key], profile[key],
                             msg="record[%r] must equal the profile value" % key)
        for key, expected in (("total_stars", 262418),
                              ("languages", {"C": 8, "OpenSCAD": 1}),
                              ("expertise_score", 1635),
                              ("primary_language", "C")):
            self.assertEqual(record[key], expected,
                             msg="record[%r] must be %r" % (key, expected))
        self.assertEqual(profile["followers"], 325466,
                         msg="the input profile dict must stay unchanged")

    def test_example_2_empty_languages_and_zero_stars(self):
        """Score Expertise example 2: stats with languages {} and
        total_stars 0, profile with followers 7 -> expertise_score 90,
        primary_language None."""
        profile = {"login": "x", "id": 1, "name": None, "company": None,
                   "location": None, "followers": 7, "public_repos": 0,
                   "created_at": None}
        stats = {"login": "x", "repo_count": 0, "non_fork_count": 0,
                 "total_stars": 0, "languages": {}}
        record = score_expertise(profile, stats)
        self.assertEqual(record["expertise_score"], 90,
                         msg="expertise_score must be round(100*log10(7+1) + 200*log10(0+1)) = 90")
        self.assertIsNone(record["primary_language"],
                          msg="primary_language must be None when languages is empty")


if __name__ == "__main__":
    unittest.main()
