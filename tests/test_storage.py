"""Tests for megatron/storage.py.

Does NOT test parsing, collection or scoring -- those belong to their own
cards' test modules. Every test uses a fresh temp SQLite file (never a
shared or network database) so tests do not interfere with each other.
"""

import json
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


class TestSaveExperts(unittest.TestCase):
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

    def test_example_1_saved_twice_upserts_to_one_row(self):
        """Example 1: saving the torvalds record twice leaves exactly 1 row."""
        save_experts(self.db_path, [TORVALDS_RECORD])
        save_experts(self.db_path, [TORVALDS_RECORD])
        conn = sqlite3.connect(self.db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM experts").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 1, msg="re-saving the same login should upsert, not duplicate")

    def test_save_experts_returns_number_written(self):
        """Behaviour: save_experts returns the number of records written."""
        written = save_experts(self.db_path, [TORVALDS_RECORD, MINNOW_RECORD])
        self.assertEqual(written, 2, msg="save_experts should return the count of records passed in")

    def test_languages_stored_as_json_string(self):
        """Behaviour: languages is stored as a JSON string in the raw table."""
        save_experts(self.db_path, [TORVALDS_RECORD])
        conn = sqlite3.connect(self.db_path)
        try:
            raw = conn.execute("SELECT languages FROM experts WHERE login=?", ("torvalds",)).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(
            json.loads(raw),
            {"C": 8, "OpenSCAD": 1},
            msg="raw languages column should be a JSON string decoding to the languages dict",
        )


class TestTopExperts(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        """Create a fresh temp db path and pre-populate it for each test."""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(self.db_path)
        save_experts(self.db_path, [TORVALDS_RECORD])
        save_experts(self.db_path, [TORVALDS_RECORD])  # saved twice per example 1
        save_experts(self.db_path, [MINNOW_RECORD])

    def tearDown(self):
        """Remove the temp db file."""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_example_2_top_expert_by_score(self):
        """Example 2: top_experts(db, 1) returns torvalds with score 850302 and decoded languages."""
        results = top_experts(self.db_path, 1)
        self.assertEqual(len(results), 1, msg="top_experts(db, 1) should return exactly one record")
        record = results[0]
        self.assertEqual(record["login"], "torvalds", msg="highest-scoring record should be torvalds")
        self.assertEqual(record["expertise_score"], 850302, msg="expertise_score should be preserved")
        self.assertEqual(
            record["languages"],
            {"C": 8, "OpenSCAD": 1},
            msg="languages should be decoded back to a dict",
        )

    def test_top_experts_ordered_descending(self):
        """Behaviour: top_experts orders by expertise_score DESC."""
        results = top_experts(self.db_path, 10)
        scores = [r["expertise_score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True), msg="results should be ordered by expertise_score DESC")
        self.assertEqual(len(results), 2, msg="both saved logins should be present")


if __name__ == "__main__":
    unittest.main()
