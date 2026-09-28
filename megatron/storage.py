"""Persist and rank Expert Records in a local SQLite database.

Card: store (decks/v1.json). Does NOT parse, collect or score anything
(those are megatron/parsers.py, megatron/collectors.py and
megatron/processors.py) and does NOT open any network connection
(Guardrail No Network In Core) -- db_path is always a local file.
"""

import json
import sqlite3
from typing import Any, Dict, List

_COLUMNS = (
    "login",
    "id",
    "name",
    "company",
    "location",
    "followers",
    "public_repos",
    "created_at",
    "total_stars",
    "languages",
    "expertise_score",
    "primary_language",
)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS experts (
    login TEXT PRIMARY KEY,
    id INTEGER,
    name TEXT,
    company TEXT,
    location TEXT,
    followers INTEGER,
    public_repos INTEGER,
    created_at TEXT,
    total_stars INTEGER,
    languages TEXT,
    expertise_score INTEGER,
    primary_language TEXT
)
"""

_UPSERT = """
INSERT INTO experts (login, id, name, company, location, followers,
                      public_repos, created_at, total_stars, languages,
                      expertise_score, primary_language)
VALUES (:login, :id, :name, :company, :location, :followers,
        :public_repos, :created_at, :total_stars, :languages,
        :expertise_score, :primary_language)
ON CONFLICT(login) DO UPDATE SET
    id=excluded.id,
    name=excluded.name,
    company=excluded.company,
    location=excluded.location,
    followers=excluded.followers,
    public_repos=excluded.public_repos,
    created_at=excluded.created_at,
    total_stars=excluded.total_stars,
    languages=excluded.languages,
    expertise_score=excluded.expertise_score,
    primary_language=excluded.primary_language
"""


def save_experts(db_path: str, records: List[Dict[str, Any]]) -> int:
    """Upsert Expert Records into the experts table, keyed by login.

    Creates the schema if it does not exist yet, upserts each record by
    login (a re-save of the same login updates the row instead of
    duplicating it), and stores languages as a JSON string since SQLite
    has no native dict column type. Returns the number of records written.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_CREATE_TABLE)
        for record in records:
            row = dict(record)
            row["languages"] = json.dumps(record["languages"])
            conn.execute(_UPSERT, row)
        conn.commit()
        return len(records)
    finally:
        conn.close()


def top_experts(db_path: str, n: int = 10) -> List[Dict[str, Any]]:
    """Return the n Expert Records with the highest expertise_score.

    Rows are ordered by expertise_score DESC; languages is decoded back
    from its stored JSON string to a dict so the caller gets the same
    shape it saved.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM experts ORDER BY expertise_score DESC LIMIT ?",
            (n,),
        )
        results = []
        for row in cursor.fetchall():
            record = {column: row[column] for column in _COLUMNS}
            record["languages"] = json.loads(record["languages"])
            results.append(record)
        return results
    finally:
        conn.close()
