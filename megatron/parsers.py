"""Parsers for GitHub API JSON: user profile and repo stats.

Reads GitHub User JSON and GitHub Repos JSON, produces Expert Profile
and Repo Stats. Stdlib only, Python 3.9-compatible.
"""

import typing

USER_KEYS = (
    "login",
    "id",
    "name",
    "company",
    "location",
    "followers",
    "public_repos",
    "created_at",
)

OPTIONAL_NONE_KEYS = ("name", "company", "location", "created_at")
COUNTER_KEYS = ("followers", "public_repos")


def parse_user_profile(data: dict) -> typing.Optional[dict]:
    """Turn a GitHub /users/<login> JSON dict into an Expert Profile."""
    profile = {}
    for key in USER_KEYS:
        value = data.get(key)
        if key in OPTIONAL_NONE_KEYS:
            profile[key] = value if value is not None else None
        elif key in COUNTER_KEYS:
            profile[key] = value if value is not None else 0
        else:  # login, id: required by the contract, kept as-is
            profile[key] = value
    return profile


def parse_repo_stats(login: str, repos: typing.List[dict]) -> dict:
    """Turn a /users/<login>/repos JSON list into Repo Stats."""
    repo_count = len(repos)
    non_fork_count = 0
    total_stars = 0
    languages: typing.Dict[str, int] = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        non_fork_count += 1
        total_stars += repo.get("stargazers_count") or 0
        language = repo.get("language")
        if language is not None:
            languages[language] = languages.get(language, 0) + 1
    return {
        "login": login,
        "repo_count": repo_count,
        "non_fork_count": non_fork_count,
        "total_stars": total_stars,
        "languages": languages,
    }
