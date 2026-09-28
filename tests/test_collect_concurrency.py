"""collect_profiles must hold at most `concurrency` logins in flight
(spec examples K.1 and K.2).

No previous test observes concurrency: the fake fetchers used elsewhere
never count calls in flight, so a collect_profiles with its semaphore
removed passes everything. Here the fake fetcher records the peak number
of concurrent calls, and the test asserts that peak equals the limit.

The criterion author is not the author of collectors.py: this file never
modifies the code under test; the module is imported and called at call
time so a mutated copy is what runs.
"""

import asyncio
import copy
import json
import os
import typing
import unittest

from megatron import collectors

FIXTURES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fixtures"
)

LOGINS = [
    "karpathy",
    "openai",
    "google",
    "huggingface",
    "rafaballerini",
]


def _load_fixture(name: str) -> typing.Any:
    with open(os.path.join(FIXTURES_DIR, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def make_fetch_json():
    """Fake fetch_json counting in-flight calls, built fresh per run.

    State dict: {"in_flight": current concurrent calls, "peak": max
    observed, "calls": total calls}. Each call increments in_flight and
    calls, records peak, awaits 0.01 s, returns a deep copy of the parsed
    fixture (repos JSON for repos paths, user JSON otherwise), then
    decrements in_flight in a finally block.
    """
    user_data = _load_fixture("user_torvalds.json")
    repos_data = _load_fixture("repos_torvalds.json")
    state = {"in_flight": 0, "peak": 0, "calls": 0}

    async def fetch_json(path: str) -> dict:
        state["in_flight"] += 1
        state["calls"] += 1
        state["peak"] = max(state["peak"], state["in_flight"])
        try:
            await asyncio.sleep(0.01)
            if path.endswith("/repos?per_page=100"):
                return copy.deepcopy(repos_data)
            return copy.deepcopy(user_data)
        finally:
            state["in_flight"] -= 1

    return fetch_json, state


class CollectConcurrencyTest(unittest.TestCase):
    maxDiff = None

    def test_k1_peak_equals_concurrency_limit_2(self):
        """K example 1: with concurrency=2 the peak in-flight calls is
        exactly 2, each login yields a result, and the fake is called
        10 times (profile + repos per login)."""
        fetch_json, state = make_fetch_json()
        result = asyncio.run(
            collectors.collect_profiles(LOGINS, fetch_json, concurrency=2)
        )
        self.assertEqual(state["peak"], 2, msg="peak in-flight calls must equal the concurrency limit 2")
        self.assertEqual(state["calls"], 10, msg="fake fetcher must be called exactly 10 times")
        self.assertEqual(len(result), 5, msg="collect_profiles must return one entry per login")
        for entry in result:
            self.assertIsNotNone(entry, msg="no login may fail: every result must be non-None")

    def test_k2_peak_equals_concurrency_limit_1(self):
        """K example 2: with concurrency=1 the peak in-flight calls is
        exactly 1 and each login yields a result."""
        fetch_json, state = make_fetch_json()
        result = asyncio.run(
            collectors.collect_profiles(LOGINS, fetch_json, concurrency=1)
        )
        self.assertEqual(state["peak"], 1, msg="peak in-flight calls must equal the concurrency limit 1")
        self.assertEqual(len(result), 5, msg="collect_profiles must return one entry per login")
        for entry in result:
            self.assertIsNotNone(entry, msg="no login may fail: every result must be non-None")


if __name__ == "__main__":
    unittest.main()
