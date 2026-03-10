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
    timestamps: list[float] = field(default_factory=list)


class RateLimiter:
    """Thread-safe sliding-window rate limiter."""

    def __init__(self, max_calls: int = 10, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._clients: dict[str, _ClientWindow] = defaultdict(_ClientWindow)
        self._lock = threading.Lock()

    def check(self, client_id: str = "global") -> None:
        now = time.time()
        with self._lock:
            window = self._clients[client_id]
            cutoff = now - self.window_seconds
            window.timestamps = [t for t in window.timestamps if t > cutoff]

            if len(window.timestamps) >= self.max_calls:
                oldest = window.timestamps[0]
                retry_after = oldest + self.window_seconds - now
                raise RateLimitExceeded(retry_after=max(retry_after, 1.0))

            window.timestamps.append(now)

    def remaining(self, client_id: str = "global") -> int:
        now = time.time()
        with self._lock:
            window = self._clients[client_id]
            cutoff = now - self.window_seconds
            window.timestamps = [t for t in window.timestamps if t > cutoff]
            return max(0, self.max_calls - len(window.timestamps))


gemini_limiter = RateLimiter(max_calls=25, window_seconds=60.0)
