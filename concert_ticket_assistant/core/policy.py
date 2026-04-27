from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from random import random

from .models import MonitorSignal, PurchaseIntent, SignalType, StrategyDecision


@dataclass
class RetryBudget:
    max_attempts: int
    attempts: int = 0

    def consume(self) -> bool:
        if self.attempts >= self.max_attempts:
            return False
        self.attempts += 1
        return True

    @property
    def exhausted(self) -> bool:
        return self.attempts >= self.max_attempts


class RateLimiter:
    """Simple sliding window limiter."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()

    def allow(self, now: float | None = None) -> bool:
        current = now if now is not None else time.monotonic()
        while self._timestamps and current - self._timestamps[0] > self.window_seconds:
            self._timestamps.popleft()

        if len(self._timestamps) >= self.max_requests:
            return False

        self._timestamps.append(current)
        return True


class RetryPolicy:
    def __init__(self, base_seconds: float = 0.2, max_seconds: float = 3.0, jitter: float = 0.15) -> None:
        self.base_seconds = base_seconds
        self.max_seconds = max_seconds
        self.jitter = jitter

    def next_delay(self, attempt: int) -> float:
        raw = min(self.base_seconds * (2 ** max(0, attempt - 1)), self.max_seconds)
        noise = 1 + (random() * 2 - 1) * self.jitter
        return max(0.0, raw * noise)


class ComplianceStrategy:
    """Select only declared target/backup options; no bypass tactics."""

    def choose(self, intent: PurchaseIntent, signal: MonitorSignal) -> StrategyDecision:
        if signal.signal_type not in (SignalType.ON_SALE, SignalType.RESTOCK):
            return StrategyDecision(matched=False, reason="Signal is not purchasable")

        allowed_sessions = [intent.session_id, *intent.backup_sessions]
        if signal.session_id not in allowed_sessions:
            return StrategyDecision(matched=False, reason="Session is outside configured scope")

        preferred_tiers = [intent.price_tier, *intent.backup_price_tiers]
        common_tier = next((tier for tier in preferred_tiers if tier in signal.price_tiers), None)
        if common_tier is None:
            return StrategyDecision(matched=False, reason="No configured price tier available")

        return StrategyDecision(
            matched=True,
            selected_session=signal.session_id,
            selected_price_tier=common_tier,
            reason="Matched configured policy",
        )

