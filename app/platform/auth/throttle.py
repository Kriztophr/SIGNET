from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import lru_cache

from app.platform.errors import ThrottledError
from app.platform.settings.config import get_settings
from app.platform.time.clock import utc_now


class LoginThrottle:
    """Sliding-window failed-login limiter keyed by account identifier.

    In-process store: correct for the single-API-container deployment this
    platform targets. Running multiple API replicas requires moving the
    window store to Redis behind this same interface.
    """

    def __init__(self, max_failures: int, window_seconds: int) -> None:
        self._max_failures = max_failures
        self._window = timedelta(seconds=window_seconds)
        self._failures: dict[str, deque[datetime]] = defaultdict(deque)

    def _prune(self, key: str, now: datetime) -> None:
        window_start = now - self._window
        failures = self._failures[key]
        while failures and failures[0] < window_start:
            failures.popleft()

    def check(self, key: str) -> None:
        """Raises ThrottledError when the key has exhausted its failure budget."""
        now = utc_now()
        self._prune(key, now)
        if len(self._failures[key]) >= self._max_failures:
            raise ThrottledError("too many failed login attempts; try again later")

    def record_failure(self, key: str) -> None:
        now = utc_now()
        self._prune(key, now)
        self._failures[key].append(now)

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


@lru_cache
def get_login_throttle() -> LoginThrottle:
    settings = get_settings()
    return LoginThrottle(settings.login_max_failures, settings.login_window_seconds)
