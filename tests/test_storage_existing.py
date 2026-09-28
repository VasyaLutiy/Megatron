"""Tests for storage.existing_logins: examples T.1-T.2 of docs/TASK_MEGATRON_V6.md."""

import os
import tempfile
import unittest

from megatron import storage


def _record(login):
    return {
        "login": login,
        "id": 1 if login == "torvalds" else 2,
        "name": login,
        "company": None,
        "location": None,
        "followers": 7,
        "public_repos": 1,
        "created_at": "2020-01-01",
        "total_stars": 0,
        "languages": {"Python": 1},
        "expertise_score": 1,
        "primary_language": "Python",
    }


TORVALDS = _record("torvalds")
MINNOW = _record("minnow")


class ExistingLoginsTest(unittest.TestCase):
    def test_t1_fresh_path_returns_empty_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "experts.db")
            result = storage.existing_logins(path)
            self.assertEqual(
                result, set(), msg="T.1: fresh path must give an empty set")

    def test_t2_saved_records_are_found_and_upsert_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "experts.db")
            storage.save_experts(path, [TORVALDS, MINNOW])
            result = storage.existing_logins(path)
            self.assertEqual(
                result, {"torvalds", "minnow"},
                msg="T.2: logins of saved records must be returned")
            storage.save_experts(path, [TORVALDS])
            result_again = storage.existing_logins(path)
            self.assertEqual(
                result_again, {"torvalds", "minnow"},
                msg="T.2: saving torvalds again leaves the set unchanged")


if __name__ == "__main__":
    unittest.main()
