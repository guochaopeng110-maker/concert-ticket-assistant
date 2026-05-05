from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from concert_ticket_assistant.core.models import MonitorSignal, SignalType


class DamaiErrorKind(str, Enum):
    NETWORK = "network_error"
    NOT_LOGGED_IN = "not_logged_in"
    RISK_CONTROL = "risk_control"
    API_CHANGED = "api_changed"
    TEMPORARY_UNAVAILABLE = "temporary_unavailable"
    PARSE_ERROR = "parse_error"


class DamaiAdapterError(RuntimeError):
    def __init__(self, message: str, kind: DamaiErrorKind, raw_payload: str = "") -> None:
        super().__init__(message)
        self.kind = kind
        self.raw_payload = raw_payload


@dataclass
class DamaiAdapter:
    name: str = "damai"
    timeout_seconds: float = 8.0
    session: Any = None

    def poll_signal(self, event_id: str, session_id: str) -> MonitorSignal:
        payload = self._fetch_subpage(event_id=event_id, session_id=session_id)
        signal_type, available_tiers = self._build_signal(payload)
        perform = payload.get("perform") if isinstance(payload, dict) else {}
        perform_id = str(perform.get("performId", "")) if isinstance(perform, dict) else ""
        return MonitorSignal(
            platform=self.name,
            event_id=event_id,
            session_id=session_id,
            signal_type=signal_type,
            official_purchase_url=f"https://detail.damai.cn/item.htm?id={event_id}",
            price_tiers=available_tiers,
            metadata={"source": "official_subpage", "perform_id": perform_id},
        )

    def _fetch_subpage(self, event_id: str, session_id: str) -> dict[str, Any]:
        params = {
            "itemId": event_id,
            "dataId": session_id or None,
            "dataType": 4,
            "apiVersion": 2.0,
            "dmChannel": "damai_pc",
            "bizCode": "ali.china.damai",
            "scenario": "itemsku",
        }
        params = {k: v for k, v in params.items() if v is not None}
        headers = {
            "accept": "*/*",
            "referer": "https://detail.damai.cn/item.htm",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        if self.session is not None:
            try:
                response = self.session.get(
                    "https://detail.damai.cn/subpage",
                    params=params,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
            except Exception as exc:
                raise DamaiAdapterError("Damai request failed", DamaiErrorKind.NETWORK) from exc
            return self._parse_subpage_payload(response.text)

        req = Request(f"https://detail.damai.cn/subpage?{urlencode(params)}", headers=headers, method="GET")
        try:
            with urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except URLError as exc:
            raise DamaiAdapterError("Damai request failed", DamaiErrorKind.NETWORK) from exc
        return self._parse_subpage_payload(body)

    @staticmethod
    def _parse_subpage_payload(payload: str) -> dict[str, Any]:
        body = payload.strip()
        lower = body.lower()
        if not body:
            raise DamaiAdapterError("Empty Damai payload", DamaiErrorKind.TEMPORARY_UNAVAILABLE, raw_payload=payload)
        if body.startswith("<"):
            if "passport.damai.cn" in lower or "login" in lower:
                raise DamaiAdapterError("Damai login required", DamaiErrorKind.NOT_LOGGED_IN, raw_payload=body)
            if any(x in body for x in ("验证码", "安全验证")) or "anti" in lower:
                raise DamaiAdapterError("Damai risk control page", DamaiErrorKind.RISK_CONTROL, raw_payload=body)
            if any(x in body for x in ("系统繁忙", "稍后再试")):
                raise DamaiAdapterError("Damai temporary page", DamaiErrorKind.TEMPORARY_UNAVAILABLE, raw_payload=body)
            raise DamaiAdapterError("Damai API changed: HTML response", DamaiErrorKind.API_CHANGED, raw_payload=body)

        if body.startswith("__jp0(") and body.endswith(")"):
            body = body[len("__jp0(") : -1]
        elif body.startswith("null(") and body.endswith(")"):
            body = body[len("null(") : -1]

        if any(x in body for x in ('"ret":["FAIL_SYS_BUSY"', "系统繁忙", "稍后再试")):
            raise DamaiAdapterError("Damai temporary payload", DamaiErrorKind.TEMPORARY_UNAVAILABLE, raw_payload=body)

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise DamaiAdapterError("Failed to parse Damai subpage payload", DamaiErrorKind.PARSE_ERROR, raw_payload=body) from exc
        if not isinstance(data, dict):
            raise DamaiAdapterError("Damai subpage payload is not an object", DamaiErrorKind.API_CHANGED, raw_payload=body)
        if "perform" not in data or "skuPagePcBuyBtn" not in data:
            raise DamaiAdapterError("Damai payload missing required fields", DamaiErrorKind.API_CHANGED, raw_payload=body)
        return data

    @staticmethod
    def _normalize_button_text(text: str) -> str:
        return "".join(text.split())

    def _build_signal(self, payload: dict[str, Any]) -> tuple[SignalType, list[str]]:
        perform = payload.get("perform", {})
        sku_list = perform.get("skuList", []) if isinstance(perform, dict) else []
        buy = payload.get("skuPagePcBuyBtn", {})
        btn_list = buy.get("skuBtnList", []) if isinstance(buy, dict) else []
        tiers: list[str] = []
        saw_sold_out = False
        saw_upcoming = False
        saw_unknown = False
        for i, sku in enumerate(sku_list):
            if i >= len(btn_list):
                continue
            btn = btn_list[i] if isinstance(btn_list[i], dict) else {}
            text = self._normalize_button_text(str(btn.get("btnText", "")))
            tier = str(sku.get("priceName") or sku.get("price") or "").strip()
            if any(k in text for k in ("立即购买", "选座购买")):
                if tier:
                    tiers.append(tier)
            elif "缺货登记" in text:
                saw_sold_out = True
            elif "即将开抢" in text:
                saw_upcoming = True
            else:
                saw_unknown = True
        if tiers:
            return SignalType.ON_SALE, tiers
        if saw_sold_out and not saw_upcoming:
            return SignalType.SOLD_OUT, tiers
        if saw_upcoming or saw_unknown:
            return SignalType.UNKNOWN, tiers
        return SignalType.UNKNOWN, tiers

