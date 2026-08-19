"""Small process-local fixed-window guard for low-cost abuse protection.

Production deployments should also enforce an aggregate limit at the gateway,
because each Gunicorn worker owns an independent in-memory bucket.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

_BUCKETS: dict[tuple[str, int], deque[float]] = defaultdict(deque)
_LOCK = Lock()


def consume_rate_limit(
    scope: str,
    user_id: int,
    *,
    limit: int,
    window_seconds: int,
) -> int:
    """Return zero when allowed, otherwise the Retry-After seconds."""
    now = time.monotonic()
    cutoff = now - max(1, window_seconds)
    key = (scope, int(user_id))
    with _LOCK:
        bucket = _BUCKETS[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= max(1, limit):
            return max(1, int(window_seconds - (now - bucket[0])))
        bucket.append(now)
    return 0
