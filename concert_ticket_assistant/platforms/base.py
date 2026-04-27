from __future__ import annotations

from typing import Protocol

from concert_ticket_assistant.core.models import MonitorSignal


class PlatformAdapter(Protocol):
    name: str

    def poll_signal(self, event_id: str, session_id: str) -> MonitorSignal:
        """Read official, user-authorized status and map it to MonitorSignal."""
        ...

