"""Tests for megatron.api_manager (examples 1-4 of Parse Rate Limit)."""

import json
import unittest
from pathlib import Path

from megatron.api_manager import parse_rate_limit, seconds_to_wait

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_header_fixture():
    # type: () -> dict
    """Parse tests/fixtures/rate_limit_headers.txt into a headers dict."""
    headers = {}
    with open(FIXTURES / "rate_limit_headers.txt", "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or ":" not in line or line.startswith("HTTP/"):
                continue
            key, _, value = line.partition(":")
            headers[key.strip().lower()] = value.strip()
    return headers


class TestParseRateLimit(unittest.TestCase):
    maxDiff = None

    def test_example_1_real_headers(self):
        """Example 1: real fixture headers -> exact Rate Limit State."""
        headers = load_header_fixture()
        self.assertEqual(
            headers.get("x-ratelimit-limit"),
            "60",
            msg="fixture must carry x-ratelimit-limit 60",
        )
        self.assertEqual(
            headers.get("x-ratelimit-remaining"),
            "59",
            msg="fixture must carry x-ratelimit-remaining 59",
        )
        self.assertEqual(
            headers.get("x-ratelimit-reset"),
            "1790594886",
            msg="fixture must carry x-ratelimit-reset 1790594886",
        )
        state = parse_rate_limit(headers)
        self.assertEqual(
            state,
            {"limit": 60, "remaining": 59, "reset": 1790594886},
            msg="parse_rate_limit must return the exact fixture state",
        )

    def test_example_1_case_insensitive(self):
        """Rule: header lookup is case-insensitive (Example 1 variant)."""
        headers = load_header_fixture()
        headers["X-RateLimit-Limit"] = headers.pop("x-ratelimit-limit")
        headers["X-RateLimit-Remaining"] = headers.pop("x-ratelimit-remaining")
        headers["X-RateLimit-Reset"] = headers.pop("x-ratelimit-reset")
        state = parse_rate_limit(headers)
        self.assertEqual(
            state,
            {"limit": 60, "remaining": 59, "reset": 1790594886},
            msg="parse_rate_limit must handle mixed-case header keys",
        )

    def test_example_4_missing_headers_give_none(self):
        """Example 4: headers with no X-RateLimit-* keys -> None."""
        result = parse_rate_limit({"content-type": "application/json"})
        self.assertIsNone(
            result,
            msg="parse_rate_limit must return None when headers are absent",
        )
        self.assertIsNone(
            parse_rate_limit({}),
            msg="parse_rate_limit must return None for an empty headers dict",
        )

    def test_tolerant_partial_headers_give_none(self):
        """Guardrail Tolerant Parser: one missing header -> None, no raise."""
        headers = load_header_fixture()
        del headers["x-ratelimit-reset"]
        result = parse_rate_limit(headers)
        self.assertIsNone(
            result,
            msg="a single missing X-RateLimit-* header must yield None",
        )


class TestSecondsToWait(unittest.TestCase):
    maxDiff = None

    def test_example_2_remaining_positive(self):
        """Example 2: remaining > 0 -> 0."""
        state = {"limit": 60, "remaining": 59, "reset": 1790594886}
        self.assertEqual(
            seconds_to_wait(state, 1790594000),
            0,
            msg="seconds_to_wait must return 0 while remaining > 0",
        )

    def test_example_3_remaining_zero(self):
        """Example 3: remaining == 0 -> reset - now (120 here)."""
        state = {"limit": 60, "remaining": 0, "reset": 1790594886}
        self.assertEqual(
            seconds_to_wait(state, 1790594766),
            120,
            msg="seconds_to_wait must return reset - now = 120",
        )

    def test_example_4_none_state(self):
        """Example 4: seconds_to_wait(None, now=1) -> 0."""
        self.assertEqual(
            seconds_to_wait(None, 1),
            0,
            msg="seconds_to_wait must return 0 for a None state",
        )

    def test_exhausted_reset_in_past_clamps_to_zero(self):
        """Rule: exhausted state with reset already past -> max(0, ...) = 0."""
        state = {"limit": 60, "remaining": 0, "reset": 1790594886}
        self.assertEqual(
            seconds_to_wait(state, 1790599999),
            0,
            msg="seconds_to_wait must clamp negative waits to 0",
        )


if __name__ == "__main__":
    unittest.main()
