"""Parse GitHub rate-limit headers and compute how long a collector must wait.

Card: ratelimit (decks/v1.json). Does NOT make any HTTP request, does NOT
retry or sleep itself -- it only reports numbers; the caller (a future
collector) decides what to do with seconds_to_wait's result.
"""

from typing import Any, Dict, Optional

_HEADER_KEYS = ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset")


def parse_rate_limit(headers: Dict[str, Any]) -> Optional[Dict[str, int]]:
    """Read case-insensitive X-RateLimit-* headers into a Rate Limit State.

    Returns None when any of the three headers is missing, rather than
    raising, so a response without rate-limit info degrades to "unknown"
    instead of killing the caller (Guardrail Tolerant Parser).
    """
    lower = {}  # type: Dict[str, Any]
    for key, value in headers.items():
        lower[key.lower()] = value

    if not all(key in lower for key in _HEADER_KEYS):
        return None

    return {
        "limit": int(lower["x-ratelimit-limit"]),
        "remaining": int(lower["x-ratelimit-remaining"]),
        "reset": int(lower["x-ratelimit-reset"]),
    }


def seconds_to_wait(state: Optional[Dict[str, int]], now: int) -> int:
    """Return how long a collector must sleep before its next call.

    0 when state is unknown (None) or quota remains; otherwise the time
    left until the reset timestamp, clamped to 0 so a reset already in the
    past never yields a negative sleep.
    """
    if state is None or state["remaining"] > 0:
        return 0
    return max(0, state["reset"] - now)
