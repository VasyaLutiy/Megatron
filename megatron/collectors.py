"""Async profile collector: fetches profile and repos per login.

The fetcher is injected as an async callable; this module opens no
sockets. Stdlib only, Python 3.9-compatible.
"""

import asyncio
import typing

from megatron.parsers import parse_repo_stats, parse_user_profile

DEFAULT_CONCURRENCY = 10


async def collect_profiles(
    logins: typing.List[str],
    fetch_json: typing.Callable[[str], typing.Awaitable[dict]],
    concurrency: int = DEFAULT_CONCURRENCY,
) -> typing.List[typing.Optional[dict]]:
    """Fetch profile + repos for every login through the injected fetcher.

    Returns a list of Expert Pairs ({"profile": ..., "stats": ...}) in the
    order of the input logins; a login whose fetch raises yields None.
    At most `concurrency` logins are in flight at once.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def one(login: str) -> typing.Optional[dict]:
        try:
            async with semaphore:
                profile_data = await fetch_json("/users/{}".format(login))
                repos_data = await fetch_json(
                    "/users/{}/repos?per_page=100".format(login)
                )
            profile = parse_user_profile(profile_data)
            stats = parse_repo_stats(login, repos_data)
            return {"profile": profile, "stats": stats}
        except Exception:
            return None

    tasks = [one(login) for login in logins]
    return list(await asyncio.gather(*tasks))
