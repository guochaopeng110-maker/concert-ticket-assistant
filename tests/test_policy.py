import unittest

from concert_ticket_assistant.core.models import MonitorSignal, PurchaseIntent, SignalType
from concert_ticket_assistant.core.policy import ComplianceStrategy, RateLimiter, RetryBudget


class PolicyTests(unittest.TestCase):
    def test_rate_limiter_blocks_after_quota(self) -> None:
        limiter = RateLimiter(max_requests=2, window_seconds=1.0)
        self.assertTrue(limiter.allow(now=100.0))
        self.assertTrue(limiter.allow(now=100.2))
        self.assertFalse(limiter.allow(now=100.4))
        self.assertTrue(limiter.allow(now=101.2))

    def test_retry_budget_exhaustion(self) -> None:
        budget = RetryBudget(max_attempts=2)
        self.assertTrue(budget.consume())
        self.assertTrue(budget.consume())
        self.assertFalse(budget.consume())
        self.assertTrue(budget.exhausted)

    def test_compliance_strategy_uses_backup_when_needed(self) -> None:
        strategy = ComplianceStrategy()
        intent = PurchaseIntent(
            event_id="evt-1",
            session_id="session-A",
            price_tier="580",
            quantity=1,
            audience_names=["A"],
            backup_sessions=["session-B"],
            backup_price_tiers=["780"],
        )
        signal = MonitorSignal(
            platform="damai",
            event_id="evt-1",
            session_id="session-B",
            signal_type=SignalType.ON_SALE,
            official_purchase_url="https://example.com",
            price_tiers=["780"],
        )
        decision = strategy.choose(intent, signal)
        self.assertTrue(decision.matched)
        self.assertEqual(decision.selected_session, "session-B")
        self.assertEqual(decision.selected_price_tier, "780")


if __name__ == "__main__":
    unittest.main()
