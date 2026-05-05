from __future__ import annotations

from dataclasses import dataclass


class AdapterErrorKind:
    NETWORK = "network_error"
    NOT_LOGGED_IN = "not_logged_in"
    RISK_CONTROL = "risk_control"
    API_CHANGED = "api_changed"
    TEMPORARY_UNAVAILABLE = "temporary_unavailable"
    PARSE_ERROR = "parse_error"


@dataclass
class AdapterError(RuntimeError):
    message: str
    kind: str
    raw_payload: str = ""

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.message)

