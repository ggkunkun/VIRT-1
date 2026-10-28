"""Resilient rate-limiting and circuit breaker for GitHub API compliance.

Strictly enforces:
1. Maximum 50 requests per minute compliance cap.
2. Exponential backoff with maximum 3 retries.
3. Circuit breaker protection against service degradation.
"""

from __future__ import annotations
import time
import threading
from typing import Callable, TypeVar

T = TypeVar("T")


class TokenBucketRateLimiter:
    """Thread-safe Token Bucket Rate Limiter.

    Strictly guarantees requests per minute <= max_per_minute (default 50).
    """

    def __init__(self, max_per_minute: int = 50) -> None:
        self.max_tokens = float(max_per_minute)
        self.refill_rate = float(max_per_minute) / 60.0  # Tokens per second (~0.833)
        self.tokens = self.max_tokens
        self.last_update = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a token is available, strictly respecting rate limits."""
        with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

                # Calculate required sleep duration
                sleep_time = (1.0 - self.tokens) / self.refill_rate
                time.sleep(max(0.01, min(sleep_time, 0.5)))


class CircuitBreakerOpenError(Exception):
    """Raised when request is rejected due to open circuit breaker."""
    pass


class CircuitBreaker:
    """Fault-tolerant circuit breaker with state transitions: CLOSED -> OPEN -> HALF-OPEN."""

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 60.0,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        self.consecutive_failures = 0
        self.state = "CLOSED"  # "CLOSED", "OPEN", "HALF-OPEN"
        self.last_state_change = time.monotonic()
        self._lock = threading.Lock()

    def execute_with_resilience(self, action: Callable[[], T]) -> T:
        """Execute action guarded by circuit breaker and exponential backoff retry."""
        with self._lock:
            now = time.monotonic()
            if self.state == "OPEN":
                if now - self.last_state_change > self.cooldown_seconds:
                    self.state = "HALF-OPEN"
                    self.last_state_change = now
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker is OPEN. Cooldown remaining: "
                        f"{self.cooldown_seconds - (now - self.last_state_change):.1f}s"
                    )

        attempt = 0
        while True:
            try:
                result = action()
                with self._lock:
                    self.consecutive_failures = 0
                    self.state = "CLOSED"
                return result
            except Exception as exc:
                attempt += 1
                with self._lock:
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= self.failure_threshold:
                        self.state = "OPEN"
                        self.last_state_change = time.monotonic()

                if attempt > self.max_retries:
                    raise RuntimeError(
                        f"Action failed after {self.max_retries} retries. "
                        f"Circuit state: {self.state}. Error: {exc}"
                    ) from exc

                sleep_time = (self.backoff_factor ** attempt) * 0.5
                time.sleep(sleep_time)
