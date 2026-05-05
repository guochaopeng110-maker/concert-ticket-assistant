from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from concert_ticket_assistant.core.models import MonitorSignal, SignalType
from concert_ticket_assistant.platforms.errors import AdapterError, AdapterErrorKind


class PiaoniuAdapterError(AdapterError):
    pass


@dataclass
class PiaoniuAdapter:
    name: str = "piaoniu"
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
            official_purchase_url=f"https://www.piaoniu.com/product/{event_id}",
            price_tiers=tiers,
            metadata={"source": "official_api"},
        )

    def _fetch_payload(self, event_id: str, session_id: str) -> dict[str, Any]:
        params = {"showId": event_id, "sessionId": session_id}
        headers = {
            "accept": "application/json, text/plain, */*",
            "referer": f"https://www.piaoniu.com/product/{event_id}",
            "user-agent": "Mozilla/5.0",
        }
        if self.session is not None:
            try:
                response = self.session.get(
                    "https://www.piaoniu.com/api/ticket/stock",
                    params=params,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
            except Exception as exc:
                raise PiaoniuAdapterError("Piaoniu request failed", AdapterErrorKind.NETWORK) from exc
            return self._parse_payload(response.text)

        req = Request(f"https://www.piaoniu.com/api/ticket/stock?{urlencode(params)}", headers=headers, method="GET")
        try:
            with urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except URLError as exc:
            raise PiaoniuAdapterError("Piaoniu request failed", AdapterErrorKind.NETWORK) from exc
        return self._parse_payload(body)

    @staticmethod
    def _parse_payload(payload: str) -> dict[str, Any]:
        body = payload.strip()
        lower = body.lower()
        if not body:
            raise PiaoniuAdapterError("Empty Piaoniu payload", AdapterErrorKind.TEMPORARY_UNAVAILABLE, body)
        if body.startswith("<"):
            if "login" in lower:
                raise PiaoniuAdapterError("Piaoniu login required", AdapterErrorKind.NOT_LOGGED_IN, body)
            if "anti" in lower or "verify" in lower or "captcha" in lower:
                raise PiaoniuAdapterError("Piaoniu risk control page", AdapterErrorKind.RISK_CONTROL, body)
            raise PiaoniuAdapterError("Piaoniu API changed: HTML response", AdapterErrorKind.API_CHANGED, body)
        if "busy" in lower or "temporary" in lower or "too many requests" in lower:
            raise PiaoniuAdapterError("Piaoniu temporary payload", AdapterErrorKind.TEMPORARY_UNAVAILABLE, body)
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise PiaoniuAdapterError("Failed to parse Piaoniu payload", AdapterErrorKind.PARSE_ERROR, body) from exc
        if not isinstance(data, dict):
            raise PiaoniuAdapterError("Piaoniu payload is not an object", AdapterErrorKind.API_CHANGED, body)
        if "data" not in data:
            raise PiaoniuAdapterError("Piaoniu payload missing required fields", AdapterErrorKind.API_CHANGED, body)
        status_code = data.get("code")
        if status_code not in (None, 0, "0"):
            message = str(data.get("message", "")).lower()
            if "login" in message:
                raise PiaoniuAdapterError("Piaoniu login required", AdapterErrorKind.NOT_LOGGED_IN, body)
            if "risk" in message or "verify" in message or "captcha" in message:
                raise PiaoniuAdapterError("Piaoniu risk control response", AdapterErrorKind.RISK_CONTROL, body)
            if "busy" in message or "temporary" in message:
                raise PiaoniuAdapterError("Piaoniu temporary payload", AdapterErrorKind.TEMPORARY_UNAVAILABLE, body)
            raise PiaoniuAdapterError("Piaoniu API returned failure code", AdapterErrorKind.API_CHANGED, body)
        return data

    def _build_signal(self, payload: dict[str, Any]) -> tuple[SignalType, list[str]]:
        data = payload.get("data", {})
        seats = data.get("skuList", []) if isinstance(data, dict) else []
        tiers: list[str] = []
        saw_sold_out = False
        saw_unknown = False
        for item in seats:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "")).strip().lower()
            tier = str(item.get("priceName") or item.get("price") or item.get("priceLabel") or "").strip()
            if status in ("on_sale", "available", "onsale", "selling"):
                if tier:
                    tiers.append(tier)
            elif status in ("sold_out", "no_stock", "offsale"):
                saw_sold_out = True
            else:
                saw_unknown = True
        if tiers:
            return SignalType.ON_SALE, tiers
        if saw_sold_out and not saw_unknown:
            return SignalType.SOLD_OUT, tiers
        return SignalType.UNKNOWN, tiers
