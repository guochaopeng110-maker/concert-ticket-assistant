from __future__ import annotations

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
    ) -> None:
        self.notifier = notifier
        self.strategy = strategy or ComplianceStrategy()
        self.limiter = limiter or RateLimiter(max_requests=4, window_seconds=1.0)
        self.retry_budget = retry_budget or RetryBudget(max_attempts=10)

    def handle_signal(self, intent: PurchaseIntent, signal: MonitorSignal, now: float | None = None) -> OrchestratorResult:
        if not self.limiter.allow(now=now):
            return OrchestratorResult(
                notified=False,
                decision=StrategyDecision(matched=False, reason="Rate limited"),
                reason="Rate limited",
            )

        if not self.retry_budget.consume():
            return OrchestratorResult(
                notified=False,
                decision=StrategyDecision(matched=False, reason="Retry budget exhausted"),
                reason="Retry budget exhausted",
            )

        decision = self.strategy.choose(intent, signal)
        if not decision.matched:
            return OrchestratorResult(notified=False, decision=decision, reason=decision.reason)

        self.notifier.send(
            title="Ticket Opportunity Found",
            body=(
                f"Platform={signal.platform} Session={decision.selected_session} "
                f"Tier={decision.selected_price_tier} URL={signal.official_purchase_url}"
            ),
        )
        return OrchestratorResult(notified=True, decision=decision, reason="Notified user")

