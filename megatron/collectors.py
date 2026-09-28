"""Concurrently collect parsed profile/stats pairs through an injected fetcher.

Card: collect (decks/v1.json). Does NOT open any socket itself and does
NOT know about urllib/requests/aiohttp -- fetch_json is the only door to
the network (Guardrail No Network In Core), so this module stays testable
offline with a fake fetcher. Does NOT score or persist anything (those are
megatron/processors.py and megatron/storage.py).
"""

import asyncio
from typing import Any, Awaitable, Callable, Dict, List, Optional

from megatron.parsers import parse_repo_stats, parse_user_profile

FetchJson = Callable[[str], Awaitable[Any]]


async def _collect_one(login: str, fetch_json: FetchJson, semaphore: "asyncio.Semaphore") -> Optional[Dict[str, Any]]:
    """Fetch and parse one login's profile+repos, or None if fetch_json raises.

    A single failing login must not abort the batch (Guardrail Tolerant
    Parser), so any exception from fetch_json is caught here and turned
    into a None entry rather than propagating out of collect_profiles.
    """
    async with semaphore:
        try:
            profile_data = await fetch_json("/users/%s" % login)
            repos_data = await fetch_json("/users/%s/repos?per_page=100" % login)
        except Exception:
            return None

    profile = parse_user_profile(profile_data)
    stats = parse_repo_stats(login, repos_data)
    return {"profile": profile, "stats": stats}


async def collect_profiles(
    logins: List[str], fetch_json: FetchJson, concurrency: int = 10
) -> List[Optional[Dict[str, Any]]]:
    """Fetch and parse profile+repos for every login, in input order.

    At most `concurrency` logins are in flight at once (asyncio.Semaphore).
    Results are returned in the order of the input logins regardless of
    completion order, since asyncio.gather preserves the order of its
    input awaitables.
    """
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [_collect_one(login, fetch_json, semaphore) for login in logins]
    return await asyncio.gather(*tasks)
