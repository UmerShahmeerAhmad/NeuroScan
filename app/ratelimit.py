"""Blocks password guessing: too many failed logins lock the login for a while.

Kept in memory, which is right for a single server process. (With several server processes
or a restart the counters start again; a production system would keep them in Redis.)
"""
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Iterable

from app.config import settings


class FailureLimiter:
    def __init__(self, window_seconds: int):
        self.window = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> Deque[float]:
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if not hits:
            self._hits.pop(key, None)
            return deque()
        return hits

    def retry_after(self, key: str, limit: int) -> int:
        """Seconds until another try is allowed (0 = allowed now)."""
        now = time.time()
        with self._lock:
            hits = self._prune(key, now)
            if len(hits) >= limit:
                return max(1, int(self.window - (now - hits[0])) + 1)
        return 0

    def add(self, keys: Iterable[str]) -> None:
        now = time.time()
        with self._lock:
            for key in keys:
                self._hits[key].append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


WINDOW = settings.LOGIN_WINDOW_MINUTES * 60
login_failures = FailureLimiter(WINDOW)
reset_requests = FailureLimiter(WINDOW)

IP_LIMIT_FACTOR = 4   # one address may fail this many times more than one account
RESET_LIMIT = 5       # password-reset emails per address per window


def describe_wait(seconds: int) -> str:
    minutes = max(1, round(seconds / 60))
    return f"{minutes} minute" + ("" if minutes == 1 else "s")
