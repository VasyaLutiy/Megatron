"""Example-based tests for megatron/api_manager.py.

Each test checks one numbered example from the spec (contour.yaml,
docs/TASK_MEGATRON.md). The author of these tests is not the author of
the code under test.
"""

import json
import os
import unittest

from megatron.api_manager import parse_rate_limit, seconds_to_wait

FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "fixtures", "rate_limit_headers.txt",
)

# Verbatim values from tests/fixtures/rate_limit_headers.txt (2026-09-28):
# x-ratelimit-limit "60", x-ratelimit-remaining "59",
# x-ratelimit-reset "1790594886"
LITERAL_HEADERS = {
    "x-ratelimit-limit": "60",
    "x-ratelimit-remaining": "59",
    "x-ratelimit-reset": "1790594886",
}
EXPECTED_STATE = {"limit": 60, "remaining": 59, "reset": 1790594886}


def _load_fixture_headers():
    """Return the real rate-limit headers as a dict.

    Reads tests/fixtures/rate_limit_headers.txt (7 lines, key: value per
    line). Falls back to the verbatim literal values only if the fixture
    file is missing from this checkout.
    """
    try:
        with open(FIXTURE, "r", encoding="utf-8") as handle:
            raw = handle.read()
    except OSError:
        return dict(LITERAL_HEADERS)
    headers = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        headers[key.strip()] = value.strip().strip('"')
    if "x-ratelimit-limit" in {k.lower() for k in headers}:
        return headers
    return dict(LITERAL_HEADERS)


class TestParseRateLimit(unittest.TestCase):
    maxDiff = None

    def test_parse_rate_limit_real_fixture_headers(self):
        """Parse Rate Limit example 1: the real headers of
        tests/fixtures/rate_limit_headers.txt as a dict yield the state
        {"limit": 60, "remaining": 59, "reset": 1790594886}."""
        headers = _load_fixture_headers()
        state = parse_rate_limit(headers)
        self.assertIsNotNone(state, "parse_rate_limit returned None for the real fixture headers")
        self.assertEqual(state, EXPECTED_STATE,
                         msg="state from real fixture headers differs from the expected Rate Limit State")


class TestSecondsToWait(unittest.TestCase):
    maxDiff = None

    def test_seconds_to_wait_zero_when_remaining_positive(self):
        """Parse Rate Limit example 2: a state with remaining 59 gives 0
        seconds to wait at now=1790594000."""
        state = {"limit": 60, "remaining": 59, "reset": 1790594886}
        result = seconds_to_wait(state, now=1790594000)
        self.assertEqual(result, 0,
                         msg="seconds_to_wait must be 0 while remaining > 0")

    def test_seconds_to_wait_120_when_exhausted(self):
        """Parse Rate Limit example 3: a state with remaining 0 and reset
        1790594886 gives 120 at now=1790594766."""
        state = {"limit": 60, "remaining": 0, "reset": 1790594886}
        result = seconds_to_wait(state, now=1790594766)
        self.assertEqual(result, 120,
                         msg="seconds_to_wait must be reset - now = 120 when remaining == 0")

    def test_missing_headers_parse_none_and_wait_zero(self):
        """Parse Rate Limit example 4 (ref: Tolerant Parser): a headers
        dict with no X-RateLimit-* keys at all makes parse_rate_limit
        return None, and seconds_to_wait(None, now=1) returns 0."""
        headers = {"content-type": "application/json", "server": "github.com"}
        state = parse_rate_limit(headers)
        self.assertIsNone(state,
                          msg="parse_rate_limit must return None when all three headers are missing")
        wait = seconds_to_wait(None, now=1)
        self.assertEqual(wait, 0,
                         msg="seconds_to_wait must return 0 for a None state")


if __name__ == "__main__":
    unittest.main()
