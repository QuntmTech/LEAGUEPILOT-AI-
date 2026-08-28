from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from threading import Lock


class LoginRateLimiter:
    """Small single-process limiter for the founder login boundary."""

    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            failures = self._failures[key]
            self._prune(failures, now)
            if len(failures) < self.limit:
                return True, 0
            retry_after = math.ceil(self.window_seconds - (now - failures[0]))
            return False, max(1, retry_after)

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            failures = self._failures[key]
            self._prune(failures, now)
            failures.append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def _prune(self, failures: deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while failures and failures[0] <= cutoff:
            failures.popleft()
