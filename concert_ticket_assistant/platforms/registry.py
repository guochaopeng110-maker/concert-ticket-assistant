from __future__ import annotations

from typing import Callable

AdapterBuilder = Callable[[], object]
_REGISTRY: dict[str, AdapterBuilder] = {}


def normalize_platform_key(name: str) -> str:
    key = (name or "").strip().lower()
    if not key:
        raise ValueError("Platform name must not be empty")
    return key


def register_platform(name: str, builder: AdapterBuilder, *, overwrite: bool = False) -> None:
    key = normalize_platform_key(name)
    if key in _REGISTRY and not overwrite:
        raise ValueError(f"Platform already registered: {key}")
    _REGISTRY[key] = builder


def build_registered_platform(name: str):
    key = normalize_platform_key(name)
    if key not in _REGISTRY:
        raise ValueError(f"Unsupported platform: {name}")
    return _REGISTRY[key]()


def list_registered_platforms() -> list[str]:
    return sorted(_REGISTRY.keys())


def clear_registry() -> None:
    _REGISTRY.clear()

