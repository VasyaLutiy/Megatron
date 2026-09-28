"""Mutants of storage.top_experts for the v7 deck (docs/TASK_MEGATRON_V7.md, section 3).

Usage: venv/bin/python decks/v7_mut.py NAME   (prints the code to append)
       venv/bin/python decks/v7_mut.py --list

Each mutant is a self-contained redefinition of top_experts appended to a temp
copy of megatron/storage.py; it shadows the real function and does not rely on
any private name of the module (a card may rename _COLUMNS).
"""

import sys

_BODY = '''

# --- v7 mutant {name}: {why}
import json as _m_json
import sqlite3 as _m_sql
_M_COLS = ("login, id, name, company, location, followers, public_repos,"
           " created_at, total_stars, languages, expertise_score, primary_language")
def top_experts(db_path, n=10):
    conn = _m_sql.connect(db_path)
    conn.row_factory = _m_sql.Row
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT " + _M_COLS + " FROM experts ORDER BY {order} LIMIT ?", (n,))]
    finally:
        conn.close()
    {post}
    for r in rows:
        r["languages"] = _m_json.loads(r["languages"])
    return rows
'''

MUTANTS = {
    "M-O1": ("tie-break removed (score only, v6 behaviour)",
             "expertise_score DESC", "pass"),
    "M-O2": ("followers key removed",
             "expertise_score DESC, login ASC", "pass"),
    "M-O3": ("login key removed",
             "expertise_score DESC, followers DESC", "pass"),
    "M-O4": ("followers ASC instead of DESC",
             "expertise_score DESC, followers ASC, login ASC", "pass"),
    "M-O5": ("login DESC instead of ASC",
             "expertise_score DESC, followers DESC, login DESC", "pass"),
    "M-O6": ("LIMIT applied before the tie-break (sorted in Python afterwards)",
             "expertise_score DESC",
             'rows.sort(key=lambda r: (-r["expertise_score"], -r["followers"], r["login"]))'),
    "M-O7": ("login compared case-insensitively",
             "expertise_score DESC, followers DESC, login COLLATE NOCASE ASC", "pass"),
}


def main(argv):
    if argv == ["--list"]:
        print(" ".join(sorted(MUTANTS)))
        return 0
    if len(argv) != 1 or argv[0] not in MUTANTS:
        print("usage: v7_mut.py NAME | --list; names: %s" % " ".join(sorted(MUTANTS)))
        return 2
    why, order, post = MUTANTS[argv[0]]
    sys.stdout.write(_BODY.format(name=argv[0], why=why, order=order, post=post))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
