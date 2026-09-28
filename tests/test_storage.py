"""Tests for megatron.storage (Store Experts), per contour.yaml examples."""

import json
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from megatron.processors import score_expertise  # noqa: E402
from megatron.parsers import parse_user_profile, parse_repo_stats  # noqa: E402
from megatron.storage import save_experts, top_experts  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _load(name):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def _torvalds_record():
    data = _load("user_torvalds.json")
    repos = _load("repos_torvalds.json")
    profile = parse_user_profile(data)
    stats = parse_repo_stats("torvalds", repos)
    return score_expertise(profile, stats)


class TestSaveExpertsUpsert(unittest.TestCase):
    maxDiff = None

    def test_example_1_save_twice_is_one_row(self):
        """Example 1: torvalds record (score 1635) saved twice into a
        fresh temp db; the experts table has exactly 1 row."""
        rec = _torvalds_record()
        self.assertEqual(
            rec["expertise_score"], 1635,
            msg="fixture-derived torvalds score must be 1635")
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "experts.db")
            self.assertEqual(
                save_experts(db_path, [rec]), 1,
                msg="first save_experts call must report 1 record written")
            self.assertEqual(
                save_experts(db_path, [rec]), 1,
                msg="second save_experts call must report 1 record written")
            conn = sqlite3.connect(db_path)
            try:
                count = conn.execute(
                    "SELECT COUNT(*) FROM experts").fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(
                count, 1, msg="experts table must hold exactly 1 row")

    def test_schema_created_if_absent(self):
        """Rule: save_experts creates the experts schema if absent."""
        rec = _torvalds_record()
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "experts.db")
            save_experts(db_path, [rec])
            conn = sqlite3.connect(db_path)
            try:
                cols = [r[1] for r in conn.execute("PRAGMA table_info(experts)")]
            finally:
                conn.close()
            self.assertEqual(
                cols,
                ["login", "id", "name", "company", "location", "followers",
                 "public_repos", "created_at", "total_stars", "languages",
                 "expertise_score", "primary_language"],
                msg="created table must match the Experts Database schema")


class TestTopExperts(unittest.TestCase):
    maxDiff = None

    def test_example_2_top_experts_orders_and_decodes(self):
        """Example 2: torvalds (1635) plus minnow (100); top_experts(db, 1)
        returns one record, login torvalds, score 1635, languages
        {"C": 8, "OpenSCAD": 1}."""
        rec = _torvalds_record()
        minnow = dict(rec)
        minnow["login"] = "minnow"
        minnow["expertise_score"] = 100
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "experts.db")
            save_experts(db_path, [rec, minnow])
            top = top_experts(db_path, 1)
            self.assertEqual(
                len(top), 1, msg="top_experts(db_path, 1) returns one record")
            self.assertEqual(
                top[0]["login"], "torvalds",
                msg="the top record is torvalds, not minnow")
            self.assertEqual(
                top[0]["expertise_score"], 1635,
                msg="top record expertise_score must be 1635")
            self.assertEqual(
                top[0]["languages"], {"C": 8, "OpenSCAD": 1},
                msg="languages must be decoded back to a dict")

    def test_top_experts_default_n_is_10_and_ordered_desc(self):
        """Rule: top_experts orders by expertise_score DESC; default n=10."""
        rec = _torvalds_record()
        records = []
        for i in range(12):
            r = dict(rec)
            r["login"] = "user_%02d" % i
            r["expertise_score"] = i * 10
            records.append(r)
        records.append(rec)  # score 1635, must come first
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "experts.db")
            save_experts(db_path, records)
            top = top_experts(db_path)
            self.assertEqual(
                len(top), 10,
                msg="default n=10 returns at most 10 records")
            self.assertEqual(
                top[0]["login"], "torvalds",
                msg="highest score must be first")
            scores = [r["expertise_score"] for r in top]
            self.assertEqual(
                scores, sorted(scores, reverse=True),
                msg="scores must be ordered DESC")

    def test_languages_stored_as_json_string_in_db(self):
        """Rule: languages is stored as a JSON string in the experts table."""
        rec = _torvalds_record()
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "experts.db")
            save_experts(db_path, [rec])
            conn = sqlite3.connect(db_path)
            try:
                stored = conn.execute(
                    "SELECT languages FROM experts WHERE login=?",
                    ("torvalds",)).fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(
                stored, json.dumps({"C": 8, "OpenSCAD": 1}),
                msg="languages column must hold the JSON string form")


if __name__ == "__main__":
    unittest.main()
