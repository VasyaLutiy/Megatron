"""Harvest CLI: fetch profiles, score, save (PaukMegatron v2.0).

No network library is imported here; the fetcher is injected. When
`main` is called without an injected fetch_json it builds a
GitHubClient lazily, inside the function.
"""

import argparse
import asyncio
import sys
import typing

from megatron import collectors, processors, storage


async def harvest(
    logins: typing.List[str],
    fetch_json: typing.Callable[[str], typing.Awaitable[dict]],
    db_path: str,
    concurrency: int = 10,
) -> typing.Dict[str, typing.Any]:
    """Collect, score and save Expert Records for every login.

    Returns {"requested": len(logins), "saved": <records written>,
    "failed": [logins whose pair is None, in input order]}.
    """
    pairs = await collectors.collect_profiles(logins, fetch_json, concurrency)
    records = []
    failed = []
    for login, pair in zip(logins, pairs):
        if pair is None:
            failed.append(login)
        else:
            records.append(processors.score_expertise(pair["profile"], pair["stats"]))
    saved = storage.save_experts(db_path, records)
    return {"requested": len(logins), "saved": saved, "failed": failed}


def main(argv=None, fetch_json=None):
    # type: (typing.Optional[typing.List[str]], typing.Optional[typing.Callable[[str], typing.Awaitable[dict]]]) -> int
    """CLI entry point: `megatron harvest <login>... [--db] [--concurrency]`."""
    parser = argparse.ArgumentParser(prog="megatron")
    sub = parser.add_subparsers(dest="command", required=True)
    p_harvest = sub.add_parser("harvest")
    p_harvest.add_argument("logins", nargs="+")
    p_harvest.add_argument("--db", default="experts.db")
    p_harvest.add_argument("--concurrency", type=int, default=10)
    args = parser.parse_args(argv)

    if fetch_json is None:
        from megatron.github_client import GitHubClient  # noqa: deferred import

        fetch_json = GitHubClient().fetch_json

    result = asyncio.run(
        harvest(args.logins, fetch_json, args.db, args.concurrency)
    )
    print("saved {} of {} -> {}".format(result["saved"], result["requested"], args.db))
    for login in result["failed"]:
        print("failed: {}".format(login), file=sys.stderr)
    return 0 if not result["failed"] else 1
