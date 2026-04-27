from __future__ import annotations

from dataclasses import dataclass

from concert_ticket_assistant.core.models import MonitorSignal, SignalType


@dataclass
class DamaiAdapter:
    """
    MVP adapter stub.
    This keeps integration compliant by exposing only official purchase URL guidance.
    """

    name: str = "damai"

    def poll_signal(self, event_id: str, session_id: str) -> MonitorSignal:
        return MonitorSignal(
            platform=self.name,
            event_id=event_id,
            session_id=session_id,
            signal_type=SignalType.UNKNOWN,
            official_purchase_url=f"https://detail.damai.cn/item.htm?id={event_id}",
            price_tiers=[],
            metadata={"source": "stub"},
        )

