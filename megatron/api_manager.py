"""Rate-limit awareness for GitHub REST API v3 responses.

parse_rate_limit(headers) reads the GitHub X-RateLimit-* response headers
(case-insensitive) into a Rate Limit State dict.
seconds_to_wait(state, now) says how long a collector must sleep.
"""

from typing import Dict, Optional


def parse_rate_limit(headers):
    # type: (Dict[str, str]) -> Optional[Dict[str, int]]
    """Return a Rate Limit State from GitHub X-RateLimit-* headers.

    The lookup is case-insensitive. Returns a dict with keys limit,
    remaining, reset when all three headers are present (any case),
    None when any of them is missing.
    """
    wanted = {
        "x-ratelimit-limit": "limit",
        "x-ratelimit-remaining": "remaining",
        "x-ratelimit-reset": "reset",
    }
    lowered = {key.lower(): key for key in headers}
    state = {}
    for header_name, state_key in wanted.items():
        if header_name not in lowered:
            return None
        try:
            state[state_key] = int(headers[lowered[header_name]])
        except (TypeError, ValueError):
            return None
    return state


def seconds_to_wait(state, now):
    # type: (Optional[Dict[str, int]], int) -> int
    """Return how many seconds a collector must sleep before the next call.

    Returns 0 when state is None or remaining > 0, otherwise
    max(0, reset - now).
    """
    if state is None:
        return 0
    if state.get("remaining", 0) > 0:
        return 0
    reset = state.get("reset", 0)
    return max(0, reset - now)
