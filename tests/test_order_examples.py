"""Independent judge test for docs/TASK_MEGATRON_V7.md, examples O.1-O.5.

Written from the spec only: the required order is expertise_score DESC,
followers DESC, login ASC (binary), applied before the limit; the order
must not depend on the order rows were inserted.
"""

import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from megatron.storage import save_experts, top_experts

BASE = {"login": None, "id": 1, "name": None, "company": None, "location": None,
        "followers": 0, "public_repos": 1, "created_at": "2011-09-03T15:26:22Z",
        "total_stars": 0, "languages": {"C": 1}, "expertise_score": 0,
        "primary_language": "C"}

# The 14 tied rows of docs/TASK_MEGATRON_V7.md section 2.1, listed in the
# required order: (login, expertise_score, followers, total_stars).
TIED_ROWS = [
    ("deepseek-ai", 1668, 106580, 669069),
    ("github", 1668, 87777, 741208),
    ("google", 1657, 79420, 684829),
    ("huggingface", 1657, 68981, 735420),
    ("ruanyf", 1563, 87692, 220179),
    ("mattpocock", 1563, 46935, 302613),
    ("lucidrains", 1532, 61572, 183638),
    ("apple", 1532, 40337, 226660),
    ("peng-zhihui", 1479, 87445, 83821),
    ("adrianhajdin", 1479, 37503, 127554),
    ("antfu", 1430, 40176, 70446),
    ("iam-veeramalla", 1430, 34295, 76125),
    ("yyx990803", 1341, 111510, 15203),
    ("geohot", 1341, 47400, 23290),
]

REQUIRED_ORDER_14 = [row[0] for row in TIED_ROWS]


def rec(login, expertise_score=0, followers=0, total_stars=0):
    return dict(BASE, login=login, expertise_score=expertise_score,
                followers=followers, total_stars=total_stars)


def recs_from_tied(order):
    table = {row[0]: row for row in TIED_ROWS}
    return [rec(login, *table[login][1:]) for login in order]


def fresh_db():
    return os.path.join(tempfile.mkdtemp(), "experts.db")


class TestOrderExamples(unittest.TestCase):
    """One test method per example O.1-O.5 of docs/TASK_MEGATRON_V7.md."""

    def test_O1_real_ties_reverse_insertion(self):
        """O.1: four tied rows saved huggingface, google, github, deepseek-ai
        (reverse of the required order) must come back deepseek-ai, github,
        google, huggingface."""
        four = ["deepseek-ai", "github", "google", "huggingface"]
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "experts.db")
            save_experts(db, recs_from_tied(list(reversed(four))))
            got = [r["login"] for r in top_experts(db, 4)]
            self.assertEqual(got, four,
                             msg="O.1: reverse-inserted tied rows must be "
                                 "returned in required order")

    def test_O2_insertion_independence_14_rows(self):
        """O.2: the 14 tied rows saved in three different orders (sorted by
        login; that reversed; a fixed shuffle) must each yield the required
        top-14 order."""
        orders = {
            "sorted by login": sorted(REQUIRED_ORDER_14),
            "reversed": list(reversed(sorted(REQUIRED_ORDER_14))),
            "shuffled": random.Random(7).sample(sorted(REQUIRED_ORDER_14), 14),
        }
        for label, order in orders.items():
            with tempfile.TemporaryDirectory() as tmp:
                db = os.path.join(tmp, "experts.db")
                save_experts(db, recs_from_tied(order))
                got = [r["login"] for r in top_experts(db, 14)]
                self.assertEqual(got, REQUIRED_ORDER_14,
                                 msg="O.2: insertion order %r must not change "
                                     "top_experts(db, 14)" % label)

    def test_O3_third_key_synthetic(self):
        """O.3: equal score and followers, insertion order carol, alice, bob,
        zed -> top order zed, alice, bob, carol (login ASC as third key)."""
        rows = [rec("carol", 1000, 500), rec("alice", 1000, 500),
                rec("bob", 1000, 500), rec("zed", 1000, 900)]
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "experts.db")
            save_experts(db, rows)
            got = [r["login"] for r in top_experts(db)]
            self.assertEqual(got, ["zed", "alice", "bob", "carol"],
                             msg="O.3: login ASC must break score+followers ties")

    def test_O4_limit_cuts_a_tie(self):
        """O.4: rows top (2000, 1), b (1000, 500), a (1000, 500) saved in that
        order -> top_experts(db, 2) == ["top", "a"]: the tie-break applies
        before the limit."""
        rows = [rec("top", 2000, 1), rec("b", 1000, 500), rec("a", 1000, 500)]
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "experts.db")
            save_experts(db, rows)
            got = [r["login"] for r in top_experts(db, 2)]
            self.assertEqual(got, ["top", "a"],
                             msg="O.4: tie-break must apply before the limit")

    def test_O5_binary_login_order(self):
        """O.5: alice (1000, 500), Bob (1000, 500) saved in that order ->
        top_experts(db) == ["Bob", "alice"]: binary comparison, "Bob" < "alice"."""
        rows = [rec("alice", 1000, 500), rec("Bob", 1000, 500)]
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "experts.db")
            save_experts(db, rows)
            got = [r["login"] for r in top_experts(db)]
            self.assertEqual(got, ["Bob", "alice"],
                             msg="O.5: login ASC must be binary collation")


if __name__ == "__main__":
    unittest.main()
