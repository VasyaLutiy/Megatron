"""Parse raw GitHub API JSON into the Expert Profile and Repo Stats shapes.

Card: parsers (decks/v1.json). Does NOT fetch anything over the network,
does NOT validate schema beyond reading the documented keys, does NOT
compute any score or ranking (that is megatron/processors.py), and does
NOT persist anything (that is megatron/storage.py).
"""

from typing import Any, Dict, List, Optional


def parse_user_profile(data: Dict[str, Any]) -> Dict[str, Any]:
    """Turn a GitHub /users/<login> JSON dict into an Expert Profile.

    Optional keys (name, company, location, created_at) default to None
    and counters (followers, public_repos) default to 0 so that a single
    malformed/partial record degrades instead of raising (Guardrail
    Tolerant Parser) -- callers batch-collecting many logins must not have
    one bad record kill the whole run.
    """
    return {
        "login": data.get("login"),
        "id": data.get("id"),
        "name": data.get("name"),
        "company": data.get("company"),
        "location": data.get("location"),
        "followers": data.get("followers") or 0,
        "public_repos": data.get("public_repos") or 0,
        "created_at": data.get("created_at"),
    }


def parse_repo_stats(login: str, repos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Turn a GitHub /users/<login>/repos JSON list into Repo Stats.

    repo_count counts every repo, including forks; non_fork_count,
    total_stars and languages count only non-fork repos, and a null
    "language" is skipped rather than recorded as a language named None --
    the contract's example fixture (12 repos, 3 forks) fixes these numbers.
    """
    repo_count = len(repos)
    non_fork_count = 0
    total_stars = 0
    languages = {}  # type: Dict[str, int]

    for repo in repos:
        if repo.get("fork"):
            continue
        non_fork_count += 1
        total_stars += repo.get("stargazers_count") or 0
        language = repo.get("language")
        if language:
            languages[language] = languages.get(language, 0) + 1

    return {
        "login": login,
        "repo_count": repo_count,
        "non_fork_count": non_fork_count,
        "total_stars": total_stars,
        "languages": languages,
    }
