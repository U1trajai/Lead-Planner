import threading
import time
from rate_limiter import RateLimiter, allow_request


def test_allowance():
    """Test that requests are allowed when under the limit."""
    limiter = RateLimiter(limit=5, window_seconds=60)
    
    for i in range(5):
        assert limiter.acquire("user1") is True, f"Request {i+1} should be allowed"
    
    print("test_allowance passed")


def test_limit_enforcement():
    """Test that requests are denied when limit is reached."""
    limiter = RateLimiter(limit=3, window_seconds=60)
    
    assert limiter.acquire("user1") is True
    assert limiter.acquire("user1") is True
    assert limiter.acquire("user1") is True
    assert limiter.acquire("user1") is False, "Request should be denied after limit"
    assert limiter.acquire("user1") is False
    
    print("test_limit_enforcement passed")


def test_window_expiry():
    """Test that old requests expire from the window."""
    limiter = RateLimiter(limit=2, window_seconds=0.5)  # 500ms window
    
    # Make 2 requests
    assert limiter.acquire("user1") is True
    assert limiter.acquire("user1") is True
    assert limiter.acquire("user1") is False
    
    # Wait for window to expire
    time.sleep(0.6)
    
    # Should be allowed again
    assert limiter.acquire("user1") is True, "Request should be allowed after window expiry"
    
    print("test_window_expiry passed")


def test_per_user_isolation():
    """Test that rate limits are enforced per user."""
    limiter = RateLimiter(limit=2, window_seconds=60)
    
    # User1 makes 2 requests
    assert limiter.acquire("user1") is True
    assert limiter.acquire("user1") is True
    assert limiter.acquire("user1") is False
    
    # User2 should still be able to make requests (each user has their own limit)
    assert limiter.acquire("user2") is True
    assert limiter.acquire("user2") is True
    assert limiter.acquire("user2") is False  # User2 also hits the limit
    
    print("test_per_user_isolation passed")


def test_invalid_limit():
    """Test that ValueError is raised for invalid limit."""
    try:
        RateLimiter(limit=0)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "limit must be greater than 0" in str(e)
    
    try:
        RateLimiter(limit=-5)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "limit must be greater than 0" in str(e)
    
    print("test_invalid_limit passed")


def test_invalid_window_seconds():
    """Test that ValueError is raised for invalid window_seconds."""
    try:
        RateLimiter(window_seconds=0)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "window_seconds must be greater than 0" in str(e)
    
    try:
        RateLimiter(window_seconds=-10)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "window_seconds must be greater than 0" in str(e)
    
    print("test_invalid_window_seconds passed")


def test_invalid_user_id():
    """Test that ValueError is raised for invalid user_id."""
    limiter = RateLimiter(limit=5, window_seconds=60)
    
    try:
        limiter.acquire("")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "user_id must be a non-empty string" in str(e)
    
    try:
        limiter.acquire(None)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "user_id must be a non-empty string" in str(e)
    
    try:
        limiter.acquire(123)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "user_id must be a non-empty string" in str(e)
    
    print("test_invalid_user_id passed")


def test_singleton_behavior():
    """Test that allow_request uses the singleton instance."""
    # Create a custom limiter with different settings
    custom = RateLimiter(limit=2, window_seconds=60)
    
    # The singleton should have default settings (limit=10)
    assert allow_request("user1") is True
    assert allow_request("user1") is True
    assert allow_request("user1") is True  # Should still be allowed (singleton has limit=10)
    
    print("test_singleton_behavior passed")


def test_thread_safety():
    """Test that the rate limiter is thread-safe."""
    limiter = RateLimiter(limit=10, window_seconds=60)
    results = []
    
    def make_requests(user_id):
        for _ in range(20):
            result = limiter.acquire(user_id)
            results.append(result)
    
    threads = []
    # All threads share the same user_id to create contention
    for i in range(10):
        t = threading.Thread(target=make_requests, args=("shared_user",))
        threads.append(t)
    
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()
    
    # Count True and False results
    true_count = sum(1 for r in results if r)
    false_count = sum(1 for r in results if not r)
    
    assert true_count == 10, f"Expected exactly 10 allowed requests, got {true_count}"
    assert false_count == 190, f"Expected exactly 190 denied requests, got {false_count}"
    
    print("test_thread_safety passed")


def test_deque_purging():
    """Test that old entries are properly purged from deque."""
    limiter = RateLimiter(limit=5, window_seconds=1.0)
    
    # Make 5 requests
    for _ in range(5):
        assert limiter.acquire("user1") is True
    
    # Should be denied now
    assert limiter.acquire("user1") is False
    
    # Wait for window to expire
    time.sleep(1.1)
    
    # Should be allowed again
    assert limiter.acquire("user1") is True
    
    print("test_deque_purging passed")


if __name__ == "__main__":
    test_allowance()
    test_limit_enforcement()
    test_window_expiry()
    test_per_user_isolation()
    test_invalid_limit()
    test_invalid_window_seconds()
    test_invalid_user_id()
    test_singleton_behavior()
    test_thread_safety()
    test_deque_purging()
    
    print("\nAll tests passed!")
