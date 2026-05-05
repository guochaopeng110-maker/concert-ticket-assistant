from __future__ import annotations

import argparse
import re
from pathlib import Path


def normalize_platform_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")
    if not normalized:
        raise ValueError("Platform name must contain letters or numbers")
    return normalized


def class_name_for(platform_name: str) -> str:
    return "".join(part.capitalize() for part in platform_name.split("_"))


def _template_init(platform_name: str) -> str:
    class_prefix = class_name_for(platform_name)
    return (
        f'"""Adapter for {platform_name} platform."""\n\n'
        f"from .adapter import {class_prefix}Adapter, {class_prefix}AdapterError\n\n"
        f'__all__ = ["{class_prefix}Adapter", "{class_prefix}AdapterError"]\n'
    )


def _template_adapter(platform_name: str) -> str:
    class_prefix = class_name_for(platform_name)
    return f"""from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from concert_ticket_assistant.core.models import MonitorSignal, SignalType
from concert_ticket_assistant.platforms.errors import AdapterError, AdapterErrorKind


class {class_prefix}AdapterError(AdapterError):
    pass


@dataclass
class {class_prefix}Adapter:
    name: str = "{platform_name}"
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
            official_purchase_url=f"https://example.com/{{event_id}}",
            price_tiers=tiers,
            metadata={{"source": "official_payload"}},
        )

    def _fetch_payload(self, event_id: str, session_id: str) -> dict[str, Any]:
        params = {{"eventId": event_id, "sessionId": session_id}}
        headers = {{"accept": "application/json", "referer": "https://example.com/"}}
        if self.session is not None:
            try:
                response = self.session.get(
                    "https://example.com/api/ticket/query",
                    params=params,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
            except Exception as exc:
                raise {class_prefix}AdapterError("{class_prefix} request failed", AdapterErrorKind.NETWORK) from exc
            return self._parse_payload(response.text)

        req = Request(f"https://example.com/api/ticket/query?{{urlencode(params)}}", headers=headers, method="GET")
        try:
            with urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except URLError as exc:
            raise {class_prefix}AdapterError("{class_prefix} request failed", AdapterErrorKind.NETWORK) from exc
        return self._parse_payload(body)

    @staticmethod
    def _parse_payload(payload: str) -> dict[str, Any]:
        body = payload.strip()
        lower = body.lower()
        if not body:
            raise {class_prefix}AdapterError("Empty {class_prefix} payload", AdapterErrorKind.TEMPORARY_UNAVAILABLE, body)
        if body.startswith("<"):
            if "login" in lower:
                raise {class_prefix}AdapterError("{class_prefix} login required", AdapterErrorKind.NOT_LOGGED_IN, body)
            if "anti" in lower or "verify" in lower:
                raise {class_prefix}AdapterError("{class_prefix} risk control page", AdapterErrorKind.RISK_CONTROL, body)
            raise {class_prefix}AdapterError("{class_prefix} API changed: HTML response", AdapterErrorKind.API_CHANGED, body)
        if "busy" in lower or "temporary" in lower:
            raise {class_prefix}AdapterError("{class_prefix} temporary payload", AdapterErrorKind.TEMPORARY_UNAVAILABLE, body)
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise {class_prefix}AdapterError("Failed to parse {class_prefix} payload", AdapterErrorKind.PARSE_ERROR, body) from exc
        if not isinstance(data, dict):
            raise {class_prefix}AdapterError("{class_prefix} payload is not an object", AdapterErrorKind.API_CHANGED, body)
        if "data" not in data:
            raise {class_prefix}AdapterError("{class_prefix} payload missing required fields", AdapterErrorKind.API_CHANGED, body)
        return data

    def _build_signal(self, payload: dict[str, Any]) -> tuple[SignalType, list[str]]:
        data = payload.get("data", {{}})
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
"""


def _template_test(platform_name: str) -> str:
    class_prefix = class_name_for(platform_name)
    return f"""import unittest
from pathlib import Path
from unittest.mock import MagicMock

from concert_ticket_assistant.core.models import SignalType
from concert_ticket_assistant.platforms.errors import AdapterErrorKind
from concert_ticket_assistant.platforms.{platform_name}.adapter import {class_prefix}Adapter, {class_prefix}AdapterError


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "{platform_name}"


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class {class_prefix}AdapterTests(unittest.TestCase):
    def test_parse_payload_matrix(self) -> None:
        cases = [
            ("payload_login.html", AdapterErrorKind.NOT_LOGGED_IN),
            ("payload_busy.json", AdapterErrorKind.TEMPORARY_UNAVAILABLE),
            ("payload_missing_fields.json", AdapterErrorKind.API_CHANGED),
        ]
        for filename, expected in cases:
            with self.assertRaises({class_prefix}AdapterError) as ctx:
                {class_prefix}Adapter._parse_payload(_fixture(filename))
            self.assertEqual(ctx.exception.kind, expected)

    def test_build_signal_detects_on_sale(self) -> None:
        payload = {class_prefix}Adapter._parse_payload(_fixture("payload_on_sale.json"))
        signal, tiers = {class_prefix}Adapter()._build_signal(payload)
        self.assertEqual(signal, SignalType.ON_SALE)
        self.assertEqual(tiers, ["380"])

    def test_poll_signal_maps_response(self) -> None:
        session = MagicMock()
        response = MagicMock()
        response.text = _fixture("payload_on_sale.json")
        response.raise_for_status.return_value = None
        session.get.return_value = response
        adapter = {class_prefix}Adapter(session=session)
        signal = adapter.poll_signal(event_id="X-1", session_id="S-1")
        self.assertEqual(signal.platform, "{platform_name}")
        self.assertEqual(signal.signal_type, SignalType.ON_SALE)
        self.assertEqual(signal.price_tiers, ["380"])


if __name__ == "__main__":
    unittest.main()
"""


FIXTURE_TEMPLATES: dict[str, str] = {
    "payload_on_sale.json": '{\n  "data": {\n    "tickets": [\n      {"status": "on_sale", "priceName": "380"},\n      {"status": "sold_out", "priceName": "580"}\n    ]\n  }\n}\n',
    "payload_login.html": "<html><body>login required</body></html>\n",
    "payload_busy.json": '{"message":"system busy, temporary unavailable"}\n',
    "payload_missing_fields.json": '{"code":0}\n',
}


def scaffold_platform(root: Path, platform_name: str) -> list[Path]:
    normalized = normalize_platform_name(platform_name)
    files: dict[Path, str] = {}

    platform_dir = root / "concert_ticket_assistant" / "platforms" / normalized
    fixture_dir = root / "tests" / "fixtures" / normalized
    test_file = root / "tests" / f"test_{normalized}_adapter.py"

    files[platform_dir / "__init__.py"] = _template_init(normalized)
    files[platform_dir / "adapter.py"] = _template_adapter(normalized)
    files[test_file] = _template_test(normalized)
    for filename, content in FIXTURE_TEMPLATES.items():
        files[fixture_dir / filename] = content

    created: list[Path] = []
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing file: {path}")
        path.write_text(content, encoding="utf-8")
        created.append(path)
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a new platform adapter with fixtures and tests.")
    parser.add_argument("--platform", required=True, help="Platform key, e.g. piaoniu")
    parser.add_argument("--root", default=".", help="Project root path (default: current directory)")
    args = parser.parse_args()

    created = scaffold_platform(Path(args.root).resolve(), args.platform)
    for path in created:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

