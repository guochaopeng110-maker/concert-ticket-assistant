from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from concert_ticket_assistant.core.models import MonitorSignal, SignalType
from concert_ticket_assistant.platforms.errors import AdapterError, AdapterErrorKind


class MaoyanErrorKind(AdapterErrorKind):
    pass


class MaoyanAdapterError(AdapterError):
    pass


@dataclass
class MaoyanAdapter:
    name: str = "maoyan"
    timeout_seconds: float = 8.0
    session: Any = None

    def poll_signal(self, event_id: str, session_id: str) -> MonitorSignal:
        payload = self._fetch_payload(event_id=event_id, session_id=session_id)
        signal_type, tiers = self._build_signal(payload)
        return MonitorSignal(
            platform=self.name,
            event_id=event_id,
            session_id=session_id,
            signal_type=signal_type,
            official_purchase_url=f"https://show.maoyan.com/detail/{event_id}",
            price_tiers=tiers,
            metadata={"source": "official_payload"},
        )

    def _fetch_payload(self, event_id: str, session_id: str) -> dict[str, Any]:
        params = {"eventId": event_id, "sessionId": session_id}
        headers = {"accept": "application/json", "referer": "https://show.maoyan.com/"}
        if self.session is not None:
            try:
                response = self.session.get(
                    "https://show.maoyan.com/api/ticket/query",
                    params=params,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
            except Exception as exc:
                raise MaoyanAdapterError("Maoyan request failed", MaoyanErrorKind.NETWORK) from exc
            return self._parse_payload(response.text)

        req = Request(f"https://show.maoyan.com/api/ticket/query?{urlencode(params)}", headers=headers, method="GET")
        try:
            with urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except URLError as exc:
            raise MaoyanAdapterError("Maoyan request failed", MaoyanErrorKind.NETWORK) from exc
        return self._parse_payload(body)

    @staticmethod
    def _parse_payload(payload: str) -> dict[str, Any]:
        body = payload.strip()
        lower = body.lower()
        if not body:
            raise MaoyanAdapterError("Empty Maoyan payload", MaoyanErrorKind.TEMPORARY_UNAVAILABLE, body)
        if body.startswith("<"):
            if "login" in lower:
                raise MaoyanAdapterError("Maoyan login required", MaoyanErrorKind.NOT_LOGGED_IN, body)
            if any(x in body for x in ("验证码", "安全验证")) or "anti" in lower:
                raise MaoyanAdapterError("Maoyan risk control page", MaoyanErrorKind.RISK_CONTROL, body)
            raise MaoyanAdapterError("Maoyan API changed: HTML response", MaoyanErrorKind.API_CHANGED, body)
        if any(x in body for x in ("系统繁忙", "稍后再试")):
            raise MaoyanAdapterError("Maoyan temporary payload", MaoyanErrorKind.TEMPORARY_UNAVAILABLE, body)
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise MaoyanAdapterError("Failed to parse Maoyan payload", MaoyanErrorKind.PARSE_ERROR, body) from exc
        if not isinstance(data, dict):
            raise MaoyanAdapterError("Maoyan payload is not an object", MaoyanErrorKind.API_CHANGED, body)
        if "data" not in data:
            raise MaoyanAdapterError("Maoyan payload missing required fields", MaoyanErrorKind.API_CHANGED, body)
        return data

    def _build_signal(self, payload: dict[str, Any]) -> tuple[SignalType, list[str]]:
        data = payload.get("data", {})
        seats = data.get("tickets", []) if isinstance(data, dict) else []
        tiers: list[str] = []
        saw_sold_out = False
        saw_unknown = False
        for item in seats:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "")).strip()
            tier = str(item.get("priceName") or item.get("price") or "").strip()
            if status in ("on_sale", "available"):
                if tier:
                    tiers.append(tier)
            elif status in ("sold_out", "no_stock"):
                saw_sold_out = True
            else:
                saw_unknown = True
        if tiers:
            return SignalType.ON_SALE, tiers
        if saw_sold_out and not saw_unknown:
            return SignalType.SOLD_OUT, tiers
        return SignalType.UNKNOWN, tiers

