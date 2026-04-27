import unittest

from concert_ticket_assistant.core.models import MonitorSignal, PurchaseIntent, SignalType
from concert_ticket_assistant.core.orchestrator import TicketOrchestrator
from concert_ticket_assistant.core.policy import RateLimiter, RetryBudget


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send(self, title: str, body: str) -> None:
        self.messages.append((title, body))


class OrchestratorTests(unittest.TestCase):
    def test_orchestrator_notifies_on_match(self) -> None:
        notifier = FakeNotifier()
        orchestrator = TicketOrchestrator(
            notifier=notifier,
            limiter=RateLimiter(max_requests=10, window_seconds=1.0),
            retry_budget=RetryBudget(max_attempts=3),
        )
        intent = PurchaseIntent(
            event_id="evt-1",
            session_id="A",
            price_tier="480",
            quantity=1,
            audience_names=["u1"],
        )
        signal = MonitorSignal(
            platform="damai",
            event_id="evt-1",
            session_id="A",
            signal_type=SignalType.RESTOCK,
            official_purchase_url="https://detail.damai.cn/item.htm?id=evt-1",
            price_tiers=["480", "680"],
        )
        result = orchestrator.handle_signal(intent, signal, now=100.0)
        self.assertTrue(result.notified)
        self.assertEqual(len(notifier.messages), 1)

    def test_orchestrator_respects_rate_limit(self) -> None:
        notifier = FakeNotifier()
        orchestrator = TicketOrchestrator(
            notifier=notifier,
            limiter=RateLimiter(max_requests=1, window_seconds=1.0),
            retry_budget=RetryBudget(max_attempts=3),
        )
        intent = PurchaseIntent(
            event_id="evt-1",
            session_id="A",
            price_tier="480",
            quantity=1,
            audience_names=["u1"],
        )
        signal = MonitorSignal(
            platform="damai",
            event_id="evt-1",
            session_id="A",
            signal_type=SignalType.ON_SALE,
            official_purchase_url="https://detail.damai.cn/item.htm?id=evt-1",
            price_tiers=["480"],
        )
        first = orchestrator.handle_signal(intent, signal, now=200.0)
        second = orchestrator.handle_signal(intent, signal, now=200.1)
        self.assertTrue(first.notified)
        self.assertFalse(second.notified)
        self.assertEqual(second.reason, "Rate limited")


if __name__ == "__main__":
    unittest.main()
