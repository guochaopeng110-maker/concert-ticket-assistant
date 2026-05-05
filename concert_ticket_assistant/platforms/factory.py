from __future__ import annotations

from concert_ticket_assistant.platforms.damai.adapter import DamaiAdapter
from concert_ticket_assistant.platforms.maoyan.adapter import MaoyanAdapter
from concert_ticket_assistant.platforms.piaoniu.adapter import PiaoniuAdapter
from concert_ticket_assistant.platforms.registry import (
    build_registered_platform,
    list_registered_platforms,
    register_platform,
)


_BOOTSTRAPPED = False


def ensure_default_platforms_registered() -> None:
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    register_platform("damai", DamaiAdapter)
    register_platform("maoyan", MaoyanAdapter)
    register_platform("piaoniu", PiaoniuAdapter)
    _BOOTSTRAPPED = True


def build_platform_adapter(platform: str):
    ensure_default_platforms_registered()
    return build_registered_platform(platform)


def list_platforms() -> list[str]:
    ensure_default_platforms_registered()
    return list_registered_platforms()
