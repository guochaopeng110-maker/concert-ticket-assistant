from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from concert_ticket_assistant.core.models import MonitorSignal, SignalType


class DamaiAdapterError(RuntimeError):
    pass


@dataclass
class DamaiAdapter:
    """Official data based signal monitor for Damai."""

    name: str = "damai"
    timeout_seconds: float = 8.0
    session: Any = None

    def poll_signal(self, event_id: str, session_id: str) -> MonitorSignal:
        payload = self._fetch_subpage(event_id=event_id, session_id=session_id)
        signal_type, available_tiers = self._build_signal(payload)
        perform = payload.get("perform") if isinstance(payload, dict) else {}
        perform_id = ""
        if isinstance(perform, dict):
            perform_id = str(perform.get("performId", ""))

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
        # Remove None values to keep request clean.
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
            response = self.session.get("https://detail.damai.cn/subpage", params=params, headers=headers, timeout=self.timeout_seconds)
            response.raise_for_status()
            return self._parse_subpage_payload(response.text)

        query = urlencode(params)
        url = f"https://detail.damai.cn/subpage?{query}"
        req = Request(url, headers=headers, method="GET")
        with urlopen(req, timeout=self.timeout_seconds) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        return self._parse_subpage_payload(body)

    @staticmethod
    def _parse_subpage_payload(payload: str) -> dict[str, Any]:
        body = payload.strip()
        if body.startswith("__jp0(") and body.endswith(")"):
            body = body[len("__jp0(") : -1]
        elif body.startswith("null(") and body.endswith(")"):
            body = body[len("null(") : -1]

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise DamaiAdapterError("Failed to parse Damai subpage payload") from exc

        if not isinstance(data, dict):
            raise DamaiAdapterError("Damai subpage payload is not an object")
        return data

    @staticmethod
    def _normalize_button_text(text: str) -> str:
        return "".join(text.split()).lower()

    def _build_signal(self, payload: dict[str, Any]) -> tuple[SignalType, list[str]]:
        perform = payload.get("perform") if isinstance(payload, dict) else None
        sku_list = perform.get("skuList", []) if isinstance(perform, dict) else []
        buy_section = payload.get("skuPagePcBuyBtn", {}) if isinstance(payload, dict) else {}
        btn_list = buy_section.get("skuBtnList", []) if isinstance(buy_section, dict) else []

        available_tiers: list[str] = []
        saw_sold_out = False
        saw_upcoming = False
        saw_unknown = False

        for idx, sku in enumerate(sku_list):
            if idx >= len(btn_list):
                continue
            btn = btn_list[idx] if isinstance(btn_list[idx], dict) else {}
            raw_text = str(btn.get("btnText", ""))
            text = self._normalize_button_text(raw_text)
            tier = str(sku.get("priceName") or sku.get("price") or "").strip()

            if "立即购买" in text or "选座购买" in text:
                if tier:
                    available_tiers.append(tier)
            elif "缺货登记" in text:
                saw_sold_out = True
            elif "即将开抢" in text:
                saw_upcoming = True
            else:
                saw_unknown = True

        if available_tiers:
            signal_type = SignalType.ON_SALE
        elif saw_sold_out and not saw_upcoming:
            signal_type = SignalType.SOLD_OUT
        elif saw_upcoming or saw_unknown:
            signal_type = SignalType.UNKNOWN
        else:
            signal_type = SignalType.UNKNOWN

        return signal_type, available_tiers
