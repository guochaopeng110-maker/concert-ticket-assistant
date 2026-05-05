"""Platform adapters for official and compliant integrations."""

from concert_ticket_assistant.platforms.factory import build_platform_adapter, list_platforms
from concert_ticket_assistant.platforms.registry import register_platform

__all__ = ["build_platform_adapter", "list_platforms", "register_platform"]
