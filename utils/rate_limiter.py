"""
Rate limiter — prevents excessive API calls (e.g. to Gemini).

Uses a sliding-window approach per client IP to limit the number of
requests within a configurable time window.
"""

import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field


class RateLimitExceeded(Exception):
    """Raised when a client exceeds the allowed request rate."""

    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded. Try again in {retry_after:.0f} seconds."
        )


@dataclass
class _ClientWindow:
    """Tracks timestamps of recent requests for one client."""
    timestamps: list[float] = field(default_factory=list)


class RateLimiter:
    """Thread-safe sliding-window rate limiter.

    Parameters
    ----------
    max_calls : int
        Maximum number of calls allowed within *window_seconds*.
    window_seconds : float
        Length of the sliding window in seconds.
    """

    def __init__(self, max_calls: int = 10, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._clients: dict[str, _ClientWindow] = defaultdict(_ClientWindow)
        self._lock = threading.Lock()

    def check(self, client_id: str = "global") -> None:
        """Check whether *client_id* is allowed to make a request.

        Raises ``RateLimitExceeded`` if the limit has been reached.
        """
        now = time.time()
        with self._lock:
            window = self._clients[client_id]
            cutoff = now - self.window_seconds
            # Remove timestamps outside the current window
            window.timestamps = [t for t in window.timestamps if t > cutoff]

            if len(window.timestamps) >= self.max_calls:
                oldest = window.timestamps[0]
                retry_after = oldest + self.window_seconds - now
                raise RateLimitExceeded(retry_after=max(retry_after, 1.0))

            window.timestamps.append(now)

    def remaining(self, client_id: str = "global") -> int:
        """Return how many calls *client_id* has left in the current window."""
        now = time.time()
        with self._lock:
            window = self._clients[client_id]
            cutoff = now - self.window_seconds
            window.timestamps = [t for t in window.timestamps if t > cutoff]
            return max(0, self.max_calls - len(window.timestamps))


# ─── Singleton instance for Gemini API calls ───
gemini_limiter = RateLimiter(max_calls=10, window_seconds=60.0)
