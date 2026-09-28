"""Example-based acceptance tests for megatron/storage.py (card store).

Independent of megatron/storage.py's own test suite: this file is the
criterion's author checking the two examples of Function Store Experts
from docs/TASK_MEGATRON.md / contour.yaml, one test per example. Every
test uses a fresh temp SQLite file, never a shared or network database.
"""

import os
import sqlite3
import tempfile
import unittest

from megatron.storage import save_experts, top_experts

TORVALDS_RECORD = {
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
    "expertise_score": 850302,
    "primary_language": "C",
}

MINNOW_RECORD = {
    "login": "minnow",
    "id": 2,
    "name": None,
    "company": None,
    "location": None,
    "followers": 100,
    "public_repos": 1,
    "created_at": None,
    "total_stars": 0,
    "languages": {},
    "expertise_score": 100,
    "primary_language": None,
}


class TestStoreExpertsExamples(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        """Create a fresh temp db path for each test."""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(self.db_path)

    def tearDown(self):
        """Remove the temp db file."""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_save_experts_example_1(self):
        """Store Experts example 1: saving the torvalds record twice leaves exactly 1 row."""
        save_experts(self.db_path, [TORVALDS_RECORD])
        save_experts(self.db_path, [TORVALDS_RECORD])

        conn = sqlite3.connect(self.db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM experts").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(
            count, 1,
            msg="example 1: saving the same login twice should upsert, leaving exactly 1 row",
        )

    def test_top_experts_example_2(self):
        """Store Experts example 2: top_experts(db, 1) returns torvalds ahead of minnow."""
        save_experts(self.db_path, [TORVALDS_RECORD])
        save_experts(self.db_path, [TORVALDS_RECORD])
        save_experts(self.db_path, [MINNOW_RECORD])

        results = top_experts(self.db_path, 1)

        self.assertEqual(
            len(results), 1,
            msg="example 2: top_experts(db_path, 1) should return exactly one record",
        )
        record = results[0]
        self.assertEqual(record["login"], "torvalds", msg="example 2: the top record's login should be torvalds")
        self.assertEqual(
            record["expertise_score"], 850302,
            msg="example 2: the top record's expertise_score should be 850302",
        )
        self.assertEqual(
            record["languages"], {"C": 8, "OpenSCAD": 1},
            msg='example 2: the top record\'s languages should equal {"C": 8, "OpenSCAD": 1}',
        )


if __name__ == "__main__":
    unittest.main()
