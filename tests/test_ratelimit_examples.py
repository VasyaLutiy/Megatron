"""Example-based acceptance tests for megatron/api_manager.py (card ratelimit).

Independent of megatron/api_manager.py's own test suite: this file is the
criterion's author checking the four examples of Function Parse Rate Limit
from docs/TASK_MEGATRON.md / contour.yaml, one test per example.
"""

import os
import unittest

from megatron.api_manager import parse_rate_limit, seconds_to_wait

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _headers_from_fixture():
    """Parse tests/fixtures/rate_limit_headers.txt lines "key: value" into a dict."""
    headers = {}
    with open(os.path.join(FIXTURES, "rate_limit_headers.txt")) as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, _, value = line.partition(":")
            headers[key.strip()] = value.strip()
    return headers


class TestParseRateLimitExamples(unittest.TestCase):
    maxDiff = None

    def test_parse_rate_limit_example_1(self):
        """Parse Rate Limit example 1: real fixture headers parse into the exact state dict."""
        headers = _headers_from_fixture()
        state = parse_rate_limit(headers)
        self.assertEqual(
            state,
            {"limit": 60, "remaining": 59, "reset": 1790594886},
            msg="example 1: parse_rate_limit(real fixture headers) should be "
            '{"limit": 60, "remaining": 59, "reset": 1790594886}',
        )

    def test_seconds_to_wait_example_2(self):
        """Parse Rate Limit example 2: remaining > 0 means seconds_to_wait is 0."""
        state = {"limit": 60, "remaining": 59, "reset": 1790594886}
        result = seconds_to_wait(state, now=1790594000)
        self.assertEqual(
            result, 0,
            msg="example 2: seconds_to_wait(state, now=1790594000) with remaining=59 should be 0",
        )

    def test_seconds_to_wait_example_3(self):
        """Parse Rate Limit example 3: remaining == 0 means the wait is reset - now."""
        state = {"limit": 60, "remaining": 0, "reset": 1790594886}
        result = seconds_to_wait(state, now=1790594766)
        self.assertEqual(
            result, 120,
            msg="example 3: seconds_to_wait(state, now=1790594766) with remaining=0, "
            "reset=1790594886 should be 120",
        )

    def test_example_4_missing_headers_tolerant_parser(self):
        """Parse Rate Limit example 4 (ref Tolerant Parser): no X-RateLimit-* headers at all."""
        headers = {"etag": 'W/"deadbeef"', "content-type": "application/json"}
        state = parse_rate_limit(headers)
        self.assertIsNone(
            state,
            msg="example 4: parse_rate_limit with no X-RateLimit-* keys at all should return None",
        )
        result = seconds_to_wait(None, now=1)
        self.assertEqual(
            result, 0,
            msg="example 4: seconds_to_wait(None, now=1) should be 0",
        )


if __name__ == "__main__":
    unittest.main()
