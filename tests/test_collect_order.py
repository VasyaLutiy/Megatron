"""collect_profiles must keep input order (spec examples C.1 and C.2).

Every v1 test feeds the same fixture to every login, so a permutation of
the results is invisible. Here each login gets a distinct profile (its
index as followers) and the fake fetcher makes later logins finish
earlier, so completion order and input order disagree.

The criterion author is not the author of collectors.py: this file never
modifies the code under test.
"""

import asyncio
import copy
import json
import os
import typing
import unittest
from unittest import mock

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
    """Fake fetch_json: later logins finish EARLIER; per-login data."""
    user_data = _load_fixture("user_torvalds.json")
    repos_data = _load_fixture("repos_torvalds.json")

    async def fetch_json(path: str) -> dict:
        for index, login in enumerate(LOGINS):
            if "/users/{}/repos?per_page=100".format(login) == path:
                await asyncio.sleep(0.01 * (5 - index))
                return copy.deepcopy(repos_data)
            if "/users/{}".format(login) == path:
                await asyncio.sleep(0.01 * (5 - index))
                profile = copy.deepcopy(user_data)
                profile["login"] = login
                profile["followers"] = index
                return profile
        raise ValueError("unexpected path: {}".format(path))

    return fetch_json


class CollectOrderTest(unittest.TestCase):
    maxDiff = None

    def _assert_input_order(self, concurrency: int) -> None:
        fetch_json = make_fetch_json()
        result = asyncio.run(
            collectors.collect_profiles(LOGINS, fetch_json, concurrency=concurrency)
        )
        self.assertEqual(
            [p["profile"]["login"] for p in result],
            LOGINS,
            msg="profile logins must equal input logins order",
        )
        self.assertEqual(
            [p["profile"]["followers"] for p in result],
            [0, 1, 2, 3, 4],
            msg="profile followers must be the per-login indices 0..4",
        )
        self.assertEqual(
            [p["stats"]["login"] for p in result],
            LOGINS,
            msg="stats logins must equal input logins order",
        )

    def test_c1_collect_profiles_keeps_input_order_concurrency_5(self):
        """C example 1: input order kept with concurrency=5 despite
        later logins finishing earlier."""
        self._assert_input_order(5)

    def test_c2_collect_profiles_keeps_input_order_concurrency_2(self):
        """C example 2: input order kept with concurrency=2 despite
        later logins finishing earlier."""
        self._assert_input_order(2)


if __name__ == "__main__":
    unittest.main()
