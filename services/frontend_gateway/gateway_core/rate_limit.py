"""A small in-memory sliding-window rate limiter.

Keyed by client identity (authenticated user id if present, else source IP),
this is deliberately simple (no Redis dependency) since the gateway is a
single-process BFF in this deployment; swapping in a distributed limiter
later only requires changing ``RateLimiter``'s storage, not any call site.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> tuple[bool, int]:
        """Returns (allowed, remaining_in_window)."""

        now = time.monotonic()
        window = self._hits[key]
        cutoff = now - self.window_seconds
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= self.max_requests:
            return False, 0
        window.append(now)
        return True, self.max_requests - len(window)

    def retry_after(self, key: str) -> float:
        window = self._hits.get(key)
        if not window:
            return 0.0
        return max(0.0, self.window_seconds - (time.monotonic() - window[0]))
