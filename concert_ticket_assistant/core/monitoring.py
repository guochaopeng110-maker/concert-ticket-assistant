from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RunMetrics:
    cycles: int = 0
    notified: int = 0
    suppressed: int = 0
    adapter_errors: int = 0
    orchestrator_skips: int = 0
    by_error_kind: dict[str, int] = field(default_factory=dict)
    consecutive_failures: int = 0
    breaker_open_until: float = 0.0

    def on_success(self, notified: bool, suppressed: bool) -> None:
        self.cycles += 1
        self.consecutive_failures = 0
        if notified:
            self.notified += 1
        if suppressed:
            self.suppressed += 1

    def on_adapter_error(self, kind: str) -> None:
        self.cycles += 1
        self.adapter_errors += 1
        self.consecutive_failures += 1
        self.by_error_kind[kind] = self.by_error_kind.get(kind, 0) + 1

    def maybe_open_breaker(self, fail_threshold: int, cooldown_seconds: float, now: float | None = None) -> bool:
        current = now if now is not None else time.monotonic()
        if self.consecutive_failures >= fail_threshold and current >= self.breaker_open_until:
            self.breaker_open_until = current + cooldown_seconds
            return True
        return False

    def breaker_open(self, now: float | None = None) -> bool:
        current = now if now is not None else time.monotonic()
        return current < self.breaker_open_until

    def log_event(self, event: str, **fields: Any) -> str:
        payload = {"event": event, "ts": int(time.time()), **fields}
        line = json.dumps(payload, ensure_ascii=False)
        print(line)
        return line


def save_error_snapshot(
    base_dir: str,
    platform: str,
    kind: str,
    cycle: int,
    event_id: str,
    session_id: str,
    payload: str,
) -> str:
    folder = Path(base_dir) / platform / kind
    folder.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    path = folder / f"{ts}-cycle{cycle}-event{event_id}-session{session_id}.txt"
    path.write_text(payload[:10000], encoding="utf-8")
    return str(path)
