from __future__ import annotations

from typing import Protocol


class NotificationProvider(Protocol):
    def send(self, title: str, body: str) -> None:
        ...

