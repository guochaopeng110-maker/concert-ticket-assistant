from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MonitorConfig:
    platform: str
    event_id: str
    session_id: str
    price_tier: str
    quantity: int = 1
    audience: list[str] | None = None
    backup_sessions: list[str] | None = None
    backup_tiers: list[str] | None = None
    interval_seconds: float = 1.0
    max_cycles: int = 0
    dedupe_window_seconds: float = 30.0
    breaker_fail_threshold: int = 5
    breaker_cooldown_seconds: float = 10.0

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "MonitorConfig":
        return MonitorConfig(
            platform=str(data.get("platform", "damai")).lower(),
            event_id=str(data["event_id"]),
            session_id=str(data["session_id"]),
            price_tier=str(data["price_tier"]),
            quantity=int(data.get("quantity", 1)),
            audience=[str(x) for x in data.get("audience", [])],
            backup_sessions=[str(x) for x in data.get("backup_sessions", [])],
            backup_tiers=[str(x) for x in data.get("backup_tiers", [])],
            interval_seconds=float(data.get("interval_seconds", 1.0)),
            max_cycles=int(data.get("max_cycles", 0)),
            dedupe_window_seconds=float(data.get("dedupe_window_seconds", 30.0)),
            breaker_fail_threshold=int(data.get("breaker_fail_threshold", 5)),
            breaker_cooldown_seconds=float(data.get("breaker_cooldown_seconds", 10.0)),
        )


def load_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    content = Path(path).read_text(encoding="utf-8")
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("Config file must contain a JSON object")
    return data
