"""Tie-break order of top_experts — examples O.1-O.5 of docs/TASK_MEGATRON_V7.md.

Required order: expertise_score DESC, followers DESC, login ASC (BINARY),
applied before LIMIT, independent of insertion order.
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

TIED = [
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


def rec(login, score, followers, total_stars=0):
    return dict(BASE, login=login, expertise_score=score,
                followers=followers, total_stars=total_stars)


def tied_records():
    return [rec(login, score, followers, stars)
            for login, score, followers, stars in TIED]


class TestTopOrder(unittest.TestCase):

    def test_o1_real_ties_reverse_insertion(self):
        # O.1: huggingface, google, github, deepseek-ai saved in that order.
        rows = tied_records()
        four = [r for r in rows if r["login"] in
                ("deepseek-ai", "github", "google", "huggingface")]
        order = ["huggingface", "google", "github", "deepseek-ai"]
        records = [next(r for r in four if r["login"] == l) for l in order]
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "experts.db")
            save_experts(db, records)
            got = [r["login"] for r in top_experts(db, 4)]
        self.assertEqual(
            got, ["deepseek-ai", "github", "google", "huggingface"],
            msg="O.1: reverse insertion must still give the required order")

    def test_o2_insertion_independence(self):
        # O.2: the 14 tied rows in three insertion orders, same top-14 list.
        rows = tied_records()
        expected = [r["login"] for r in rows]
        by_login = sorted(rows, key=lambda r: r["login"])
        orders = [
            by_login,
            list(reversed(by_login)),
            [r for r in rows if r["login"] in
             random.Random(7).sample(sorted(r["login"] for r in rows), 14)],
        ]
        shuffled = random.Random(7).sample(sorted(r["login"] for r in rows), 14)
        third = [next(r for r in rows if r["login"] == l) for l in shuffled]
        orders[2] = third
        results = []
        with tempfile.TemporaryDirectory() as tmp:
            for i, order in enumerate(orders):
                db = os.path.join(tmp, "experts%d.db" % i)
                save_experts(db, order)
                results.append([r["login"] for r in top_experts(db, 14)])
        self.assertEqual(
            results[0], expected,
            msg="O.2: order by login gives the required order")
        self.assertEqual(
            results[1], expected,
            msg="O.2: reversed insertion gives the required order")
        self.assertEqual(
            results[2], expected,
            msg="O.2: shuffled insertion gives the required order")
        self.assertEqual(
            results[0], results[1],
            msg="O.2: lists from different insertion orders are equal")
        self.assertEqual(
            results[1], results[2],
            msg="O.2: lists from different insertion orders are equal")

    def test_o3_third_key_synthetic(self):
        # O.3: carol, alice, bob, zed all score 1000; zed has more followers.
        records = [rec("carol", 1000, 500), rec("alice", 1000, 500),
                   rec("bob", 1000, 500), rec("zed", 1000, 900)]
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "experts.db")
            save_experts(db, records)
            got = [r["login"] for r in top_experts(db)]
        self.assertEqual(
            got, ["zed", "alice", "bob", "carol"],
            msg="O.3: followers DESC breaks score ties, login ASC the rest")

    def test_o4_limit_cuts_a_tie(self):
        # O.4: the tie-break applies before LIMIT.
        records = [rec("top", 2000, 1), rec("b", 1000, 500),
                   rec("a", 1000, 500)]
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "experts.db")
            save_experts(db, records)
            got = [r["login"] for r in top_experts(db, 2)]
        self.assertEqual(
            got, ["top", "a"],
            msg="O.4: the limit cuts the tie-broken order, not before it")

    def test_o5_binary_login_order(self):
        # O.5: binary collation, "Bob" < "alice".
        records = [rec("alice", 1000, 500), rec("Bob", 1000, 500)]
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "experts.db")
            save_experts(db, records)
            got = [r["login"] for r in top_experts(db)]
        self.assertEqual(
            got, ["Bob", "alice"],
            msg="O.5: login tie-break uses binary comparison")


if __name__ == "__main__":
    unittest.main()
