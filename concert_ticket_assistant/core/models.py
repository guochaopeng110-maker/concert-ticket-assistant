from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SignalType(str, Enum):
    ON_SALE = "on_sale"
    RESTOCK = "restock"
    SOLD_OUT = "sold_out"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PurchaseIntent:
    event_id: str
    session_id: str
    price_tier: str
    quantity: int
    audience_names: list[str]
    backup_sessions: list[str] = field(default_factory=list)
    backup_price_tiers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MonitorSignal:
    platform: str
    event_id: str
    session_id: str
    signal_type: SignalType
    official_purchase_url: str
    price_tiers: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyDecision:
    matched: bool
    selected_session: str | None = None
    selected_price_tier: str | None = None
    reason: str = ""

