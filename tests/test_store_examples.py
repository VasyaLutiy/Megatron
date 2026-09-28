"""Example-based tests for megatron/storage.py (Store Experts)."""

import json
import os
import tempfile
import unittest

from megatron.storage import save_experts, top_experts


def _torvalds_record():
    # type: () -> dict
    """Expert Record built from the fixture numbers (contour.yaml examples)."""
    return {
        "login": "torvalds",
        "id": 1024025,
        "name": "Linus Torvalds",
        "company": None,
        "location": "Portland, OR",
        "followers": 325466,
        "public_repos": 12,
        "created_at": "2011-09-06T18:54:47Z",
        "total_stars": 262418,
        "languages": {"C": 8, "OpenSCAD": 1},
        "expertise_score": 850302,
        "primary_language": "C",
    }


def _minnow_record():
    # type: () -> dict
    """Second record for example 2: login 'minnow', score 100."""
    rec = _torvalds_record()
    rec["login"] = "minnow"
    rec["expertise_score"] = 100
    return rec


class StoreExpertsTests(unittest.TestCase):
    def setUp(self):
        # type: () -> None
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        os.remove(self.db_path)
        self.addCleanup(lambda: os.path.exists(self.db_path)
                        and os.remove(self.db_path))

    def test_save_experts_upsert_same_login_one_row(self):
        # type: () -> None
        """Store Experts example 1: torvalds record saved twice -> exactly 1 row."""
        rec = _torvalds_record()
        save_experts(self.db_path, [rec])
        save_experts(self.db_path, [rec])
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM experts").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 1, msg="upsert by login must keep exactly 1 row")

    def test_top_experts_orders_by_score_desc_and_decodes_languages(self):
        # type: () -> None
        """Store Experts example 2: minnow (100) + torvalds (850302); top 1."""
        save_experts(self.db_path, [_torvalds_record(), _minnow_record()])
        result = top_experts(self.db_path, 1)
        self.assertEqual(len(result), 1, msg="top_experts(db, 1) returns 1 record")
        self.assertEqual(result[0]["login"], "torvalds",
                         msg="highest score record is torvalds")
        self.assertEqual(result[0]["expertise_score"], 850302,
                         msg="expertise_score is 850302")
        self.assertEqual(result[0]["languages"], {"C": 8, "OpenSCAD": 1},
                         msg="languages decoded back to a dict")


if __name__ == "__main__":
    unittest.main()
