import threading
import time
from collections import deque


class RateLimiter:
    """Rate limiter enforcing a maximum of requests per sliding window per user."""

    def __init__(self, limit: int = 10, window_seconds: float = 60):
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than 0")
        
        self._limit = limit
        self._window_seconds = window_seconds
        self._timestamps = {}  # user_id -> deque of timestamps
        self._lock = threading.Lock()

    def acquire(self, user_id: str) -> bool:
        """Acquire a slot in the rate limit for the given user.
        
        Returns True if the request is allowed, False otherwise.
        """
        if not isinstance(user_id, str) or len(user_id) == 0:
            raise ValueError("user_id must be a non-empty string")
        
        with self._lock:
            now = time.time()
            
            # Initialize deque for new user
            if user_id not in self._timestamps:
                self._timestamps[user_id] = deque()
            
            timestamps = self._timestamps[user_id]
            
            # Purge old entries outside the window
            cutoff = now - self._window_seconds
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()
            
            # Check if under limit
            if len(timestamps) < self._limit:
                timestamps.append(now)
                return True
            
            return False


# Singleton instance
_default_limiter = RateLimiter()


def allow_request(user_id: str) -> bool:
    """Helper function that forwards to the singleton rate limiter."""
    return _default_limiter.acquire(user_id)
