from __future__ import annotations

from concert_ticket_assistant.platforms.damai.adapter import DamaiAdapter
from concert_ticket_assistant.platforms.maoyan.adapter import MaoyanAdapter


def build_platform_adapter(platform: str):
    key = (platform or "").strip().lower()
    if key == "damai":
        return DamaiAdapter()
    if key == "maoyan":
        return MaoyanAdapter()
    raise ValueError(f"Unsupported platform: {platform}")

