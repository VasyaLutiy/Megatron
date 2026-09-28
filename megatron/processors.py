"""Score a parsed profile/stats pair into an Expert Record.

Card: score (decks/v1.json). Does NOT parse raw GitHub JSON (that is
megatron/parsers.py), does NOT fetch or collect anything (that is
megatron/collectors.py), and does NOT persist anything (that is
megatron/storage.py).
"""

from typing import Any, Dict, Optional


def score_expertise(profile: Dict[str, Any], stats: Dict[str, Any]) -> Dict[str, Any]:
    """Merge an Expert Profile and its Repo Stats into an Expert Record.

    expertise_score = followers + 2 * total_stars, fixed by the contract
    (torvalds fixture -> 325466 + 2*262418 = 850302). primary_language is
    the highest-count language, ties broken lexicographically so the result
    is deterministic; None when there are no languages at all. The record
    is the profile dict extended in place, not a second serialization of
    its fields.
    """
    languages = stats["languages"]
    total_stars = stats["total_stars"]

    if languages:
        # max() picks the first item for equal counts when candidates are
        # visited in ascending key order, giving the lexicographic tie-break.
        primary_language = max(sorted(languages), key=lambda lang: languages[lang])
    else:
        primary_language = None

    record = dict(profile)
    record["total_stars"] = total_stars
    record["languages"] = languages
    record["expertise_score"] = profile["followers"] + 2 * total_stars
    record["primary_language"] = primary_language
    return record
