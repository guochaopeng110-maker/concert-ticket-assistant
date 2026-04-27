from __future__ import annotations


class ConsoleNotifier:
    def send(self, title: str, body: str) -> None:
        print(f"[{title}] {body}")

