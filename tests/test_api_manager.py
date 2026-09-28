"""Tests for megatron/api_manager.py.

Does NOT test parsing of profile/repo JSON or collection -- those belong to
their own cards' test modules. Uses only tests/fixtures/rate_limit_headers.txt
and inline dicts, never a live HTTP response.
"""

import os
import unittest

from megatron.api_manager import parse_rate_limit, seconds_to_wait

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_headers_dict():
    """Parse tests/fixtures/rate_limit_headers.txt into a lowercase dict."""
    headers = {}
    with open(os.path.join(FIXTURES, "rate_limit_headers.txt")) as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, _, value = line.partition(":")
            headers[key.strip()] = value.strip()
    return headers


class TestParseRateLimit(unittest.TestCase):
    maxDiff = None

    def test_example_1_real_headers_fixture(self):
        """Example 1: the real rate_limit_headers.txt parses to the documented state."""
        headers = _load_headers_dict()
        state = parse_rate_limit(headers)
        self.assertEqual(
            state,
            {"limit": 60, "remaining": 59, "reset": 1790594886},
            msg="parsed state should match the fixture's X-RateLimit-* values",
        )

    def test_example_4_missing_headers_tolerant_parser(self):
        """Example 4 (ref Tolerant Parser): no X-RateLimit-* keys returns None."""
        state = parse_rate_limit({"etag": 'W/"abc"'})
        self.assertIsNone(state, msg="parse_rate_limit should return None when headers are absent")

    def test_case_insensitive_header_keys(self):
        """Behaviour: header lookup is case-insensitive (rule, not a numbered example)."""
        state = parse_rate_limit(
            {
                "X-RateLimit-Limit": "60",
                "X-RateLimit-Remaining": "59",
                "X-RateLimit-Reset": "1790594886",
            }
        )
        self.assertEqual(
            state,
            {"limit": 60, "remaining": 59, "reset": 1790594886},
            msg="parse_rate_limit should accept mixed-case header names",
        )


class TestSecondsToWait(unittest.TestCase):
    maxDiff = None

    def test_example_2_remaining_quota_no_wait(self):
        """Example 2: remaining > 0 means seconds_to_wait is 0."""
        state = {"limit": 60, "remaining": 59, "reset": 1790594886}
        self.assertEqual(
            seconds_to_wait(state, now=1790594000),
            0,
            msg="seconds_to_wait should be 0 while remaining quota exists",
        )

    def test_example_3_exhausted_quota_waits_until_reset(self):
        """Example 3: remaining 0 waits until reset - now (120 seconds)."""
        state = {"limit": 60, "remaining": 0, "reset": 1790594886}
        self.assertEqual(
            seconds_to_wait(state, now=1790594766),
            120,
            msg="seconds_to_wait should equal reset - now when quota is exhausted",
        )

    def test_example_4_none_state_no_wait(self):
        """Example 4 (ref Tolerant Parser): seconds_to_wait(None, now) is 0."""
        self.assertEqual(
            seconds_to_wait(None, now=1),
            0,
            msg="seconds_to_wait should be 0 when state is unknown (None)",
        )

    def test_reset_in_past_clamped_to_zero(self):
        """Behaviour: max(0, reset - now) never returns a negative wait."""
        state = {"limit": 60, "remaining": 0, "reset": 100}
        self.assertEqual(
            seconds_to_wait(state, now=200),
            0,
            msg="seconds_to_wait should clamp a past reset to 0, not go negative",
        )


if __name__ == "__main__":
    unittest.main()
