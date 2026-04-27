from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from .models import MonitorSignal, PurchaseIntent, StrategyDecision
from .policy import ComplianceStrategy, RateLimiter, RetryBudget


class Notifier(Protocol):
    def send(self, title: str, body: str) -> None:
        ...


@dataclass
class OrchestratorResult:
    notified: bool
    decision: StrategyDecision
    reason: str


class TicketOrchestrator:
    def __init__(
        self,
        notifier: Notifier,
        strategy: ComplianceStrategy | None = None,
        limiter: RateLimiter | None = None,
        retry_budget: RetryBudget | None = None,
        dedupe_window_seconds: float = 30.0,
    ) -> None:
        self.notifier = notifier
        self.strategy = strategy or ComplianceStrategy()
        self.limiter = limiter or RateLimiter(max_requests=4, window_seconds=1.0)
        self.retry_budget = retry_budget or RetryBudget(max_attempts=10)
        self.dedupe_window_seconds = dedupe_window_seconds
        self._last_notified_at: dict[str, float] = {}

    def handle_signal(self, intent: PurchaseIntent, signal: MonitorSignal, now: float | None = None) -> OrchestratorResult:
        current = now if now is not None else time.monotonic()

        if not self.limiter.allow(now=now):
            return OrchestratorResult(
                notified=False,
                decision=StrategyDecision(matched=False, reason="Rate limited"),
                reason="Rate limited",
            )

        decision = self.strategy.choose(intent, signal)
        if not decision.matched:
            return OrchestratorResult(notified=False, decision=decision, reason=decision.reason)

        dedupe_key = (
            f"{signal.platform}:{signal.event_id}:{decision.selected_session}:{decision.selected_price_tier}"
        )
        last_notified = self._last_notified_at.get(dedupe_key)
        if last_notified is not None and current - last_notified < self.dedupe_window_seconds:
            return OrchestratorResult(notified=False, decision=decision, reason="Duplicate suppressed")

        if not self.retry_budget.consume():
            return OrchestratorResult(
                notified=False,
                decision=StrategyDecision(matched=False, reason="Retry budget exhausted"),
                reason="Retry budget exhausted",
            )

        self.notifier.send(
            title="Ticket Opportunity Found",
            body=(
                f"Platform={signal.platform} Session={decision.selected_session} "
                f"Tier={decision.selected_price_tier} URL={signal.official_purchase_url}"
            ),
        )
        self._last_notified_at[dedupe_key] = current
        return OrchestratorResult(notified=True, decision=decision, reason="Notified user")
