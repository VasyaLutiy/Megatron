"""SQLite persistence and ranking of expert records (PaukMegatron v1.0)."""

import json
import sqlite3
from typing import Any, Dict, List

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS experts ("
    " login TEXT PRIMARY KEY,"
    " id INTEGER,"
    " name TEXT,"
    " company TEXT,"
    " location TEXT,"
    " followers INTEGER,"
    " public_repos INTEGER,"
    " created_at TEXT,"
    " total_stars INTEGER,"
    " languages TEXT,"
    " expertise_score INTEGER,"
    " primary_language TEXT"
    ")"
)

_COLUMNS = (
    "login, id, name, company, location, followers, public_repos,"
    " created_at, total_stars, languages, expertise_score, primary_language"
)


def save_experts(db_path, records):
    # type: (str, List[Dict[str, Any]]) -> int
    """Upsert Expert Records into the experts table keyed by login.

    Creates the schema if absent; stores languages as a JSON string.
    Returns the number of records written.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_SCHEMA)
        written = 0
        for rec in records:
            conn.execute(
                "INSERT INTO experts (" + _COLUMNS + ") VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(login) DO UPDATE SET"
                " id=excluded.id, name=excluded.name,"
                " company=excluded.company, location=excluded.location,"
                " followers=excluded.followers,"
                " public_repos=excluded.public_repos,"
                " created_at=excluded.created_at,"
                " total_stars=excluded.total_stars,"
                " languages=excluded.languages,"
                " expertise_score=excluded.expertise_score,"
                " primary_language=excluded.primary_language",
                (
                    rec["login"],
                    rec["id"],
                    rec["name"],
                    rec["company"],
                    rec["location"],
                    rec["followers"],
                    rec["public_repos"],
                    rec["created_at"],
                    rec["total_stars"],
                    json.dumps(rec["languages"]),
                    rec["expertise_score"],
                    rec["primary_language"],
                ),
            )
            written += 1
        conn.commit()
        return written
    finally:
        conn.close()


def top_experts(db_path, n=10):
    # type: (str, int) -> List[Dict[str, Any]]
    """Return the n records with the highest expertise_score, DESC.

    Ties are broken by followers DESC, then login ASC, independent of
    insertion order.
    languages is decoded back to a dict; rows come back as Expert Records.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT " + _COLUMNS + " FROM experts"
            " ORDER BY expertise_score DESC, followers DESC, login ASC"
            " LIMIT ?",
            (n,),
        )
        out = []
        for row in cur.fetchall():
            rec = dict(row)
            rec["languages"] = json.loads(rec["languages"])
            out.append(rec)
        return out
    finally:
        conn.close()


def existing_logins(db_path):
    # type: (str) -> Set[str]
    """Return the set of login values in the experts table.

    A db without the table (a fresh path, an empty file) gives set();
    this function never raises for that and never writes rows.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='experts'"
        )
        if cur.fetchone() is None:
            return set()
        return {row[0] for row in conn.execute("SELECT login FROM experts")}
    finally:
        conn.close()
