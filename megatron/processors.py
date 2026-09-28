"""Expertise scoring over parsed profile data (PaukMegatron v1.0)."""

import math
from typing import Any, Dict, Optional


def score_expertise(profile, stats):
    # type: (Dict[str, Any], Dict[str, Any]) -> Dict[str, Any]
    """Merge an Expert Profile and its Repo Stats into an Expert Record.

    expertise_score = round(100*log10(followers+1) + 200*log10(total_stars+1)).
    primary_language is the language with the highest count in
    stats["languages"], ties broken by lexicographic order, or None when
    languages is empty. The record carries the Expert Profile keys plus
    total_stars, languages, expertise_score, primary_language; the profile
    dict itself is not copied a second time.
    """
    total_stars = stats.get("total_stars", 0)
    languages = stats.get("languages", {})

    score = round(100 * math.log10(profile.get("followers", 0) + 1) + 200 * math.log10(total_stars + 1))

    if languages:
        primary_language = max(sorted(languages), key=lambda lang: languages[lang])
    else:
        primary_language = None

    record = dict(profile)
    record["total_stars"] = total_stars
    record["languages"] = languages
    record["expertise_score"] = score
    record["primary_language"] = primary_language
    return record
