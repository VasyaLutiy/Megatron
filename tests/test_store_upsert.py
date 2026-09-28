"""U example 1: save_experts must UPDATE the row, not ignore a second insert."""

import copy
import os
import sqlite3
import tempfile
import unittest
from typing import Any, Dict, List

from megatron import storage

# type: ignore


def _record_a():
    # type: () -> Dict[str, Any]
    """Record A — torvalds, verbatim from spec section 2.1."""
    return {
        "login": "torvalds",
        "id": 1024025,
        "name": "Linus Torvalds",
        "company": "Linux Foundation",
        "location": "Portland, OR",
        "followers": 325466,
        "public_repos": 12,
        "created_at": "2011-09-03T15:26:22Z",
        "total_stars": 262418,
        "languages": {"C": 8, "OpenSCAD": 1},
        "expertise_score": 1635,
        "primary_language": "C",
    }


def _record_b():
    # type: () -> Dict[str, Any]
    """Record B — same login as stored by the live smoke run (spec 2.1)."""
    rec = copy.deepcopy(_record_a())
    rec["followers"] = 325474
    rec["total_stars"] = 262428
    rec["expertise_score"] = 1635
    return rec


class StoreUpsertTests(unittest.TestCase):
    maxDiff = None

    def test_upsert_updates_row(self):
        # type: () -> None
        """U example 1: second save_experts of same login updates the row."""
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "experts.sqlite")
            self.assertEqual(storage.save_experts(db, [_record_a()]), 1,
                             msg="first save returns 1")
            self.assertEqual(storage.save_experts(db, [_record_b()]), 1,
                             msg="second save returns 1")
            conn = sqlite3.connect(db)
            try:
                count = conn.execute(
                    "SELECT COUNT(*) FROM experts").fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(count, 1,
                             msg="upsert by login keeps exactly 1 row")
            expected = [_record_b()]
            actual = storage.top_experts(db, 10)
            self.assertEqual(actual, expected,
                             msg="top_experts returns exactly [B] with "
                                 "followers 325474, total_stars 262428, "
                                 "expertise_score 1635")
            self.assertEqual(actual[0]["followers"], 325474,
                             msg="followers updated to 325474")
            self.assertEqual(actual[0]["total_stars"], 262428,
                             msg="total_stars updated to 262428")
            self.assertEqual(actual[0]["expertise_score"], 1635,
                             msg="expertise_score of B is 1635")


if __name__ == "__main__":
    unittest.main()
