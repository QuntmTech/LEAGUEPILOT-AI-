from __future__ import annotations

import ipaddress
import time
from collections import OrderedDict, deque
from threading import Lock

# Two independent budgets. The identifier budget stops an attacker grinding one account
# from many sources; the network budget stops them spraying many accounts from one source.
# Neither alone is sufficient, so a request must satisfy both.
IDENTIFIER_LIMIT = 10
NETWORK_LIMIT = 30
WINDOW_SECONDS = 900

# Storage ceiling per dimension. Keys are attacker-supplied, so an unbounded map is itself
# a denial-of-service vector; least-recently-touched entries are evicted past this.
MAX_TRACKED_KEYS = 4096


def normalize_identifier(value: str) -> str:
    """Fold an email to one key so case and padding cannot buy extra attempts."""
    return value.strip().casefold()


def normalize_network(address: str | None) -> str:
    """Reduce a client address to the unit we budget.

    IPv6 is bucketed to /64: a single host is routinely handed that whole range, so
    counting individual addresses there would let one attacker mint an unlimited number
    of fresh budgets. IPv4 is counted per address — aggregating further would let one
    abusive client lock out everyone behind a shared NAT.
    """
    if not address:
        return "unknown"
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return "unknown"
    if parsed.version == 6:
        return str(ipaddress.ip_network(f"{parsed}/64", strict=False))
    return str(parsed)


class FailureThrottle:
    """Sliding-window failure counter, bounded in both time and size.

    Deliberately *not* a lockout. Entries decay out of the window on their own, so an
    attacker cannot use it to keep a victim's account permanently unusable — the worst
    they can do is impose a delay that clears itself. Nothing here is ever surfaced to
    the caller in a way that distinguishes a real account from an unknown one.
    """

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int = WINDOW_SECONDS,
        max_keys: int = MAX_TRACKED_KEYS,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._max_keys = max_keys
        self._failures: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def _prune(self, failures: deque[float], now: float) -> None:
        cutoff = now - self._window
        while failures and failures[0] <= cutoff:
            failures.popleft()

    def _evict(self) -> None:
        while len(self._failures) > self._max_keys:
            self._failures.popitem(last=False)

    def allows(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            failures = self._failures.get(key)
            if failures is None:
                return True
            self._prune(failures, now)
            if not failures:
                self._failures.pop(key, None)
                return True
            return len(failures) < self._limit

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            failures = self._failures.get(key)
            if failures is None:
                failures = deque()
                self._failures[key] = failures
            self._prune(failures, now)
            failures.append(now)
            self._failures.move_to_end(key)
            self._evict()

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()
