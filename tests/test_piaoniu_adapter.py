import unittest
from pathlib import Path
from unittest.mock import MagicMock

from concert_ticket_assistant.core.models import SignalType
from concert_ticket_assistant.platforms.errors import AdapterErrorKind
from concert_ticket_assistant.platforms.piaoniu.adapter import PiaoniuAdapter, PiaoniuAdapterError


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "piaoniu"


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class PiaoniuAdapterTests(unittest.TestCase):
    def test_parse_payload_matrix(self) -> None:
        cases = [
            ("payload_login.html", AdapterErrorKind.NOT_LOGGED_IN),
            ("payload_busy.json", AdapterErrorKind.TEMPORARY_UNAVAILABLE),
            ("payload_missing_fields.json", AdapterErrorKind.API_CHANGED),
        ]
        for filename, expected in cases:
            with self.assertRaises(PiaoniuAdapterError) as ctx:
                PiaoniuAdapter._parse_payload(_fixture(filename))
            self.assertEqual(ctx.exception.kind, expected)

    def test_build_signal_detects_on_sale(self) -> None:
        payload = PiaoniuAdapter._parse_payload(_fixture("payload_on_sale.json"))
        signal, tiers = PiaoniuAdapter()._build_signal(payload)
        self.assertEqual(signal, SignalType.ON_SALE)
        self.assertEqual(tiers, ["380"])

    def test_poll_signal_maps_response(self) -> None:
        session = MagicMock()
        response = MagicMock()
        response.text = _fixture("payload_on_sale.json")
        response.raise_for_status.return_value = None
        session.get.return_value = response
        adapter = PiaoniuAdapter(session=session)
        signal = adapter.poll_signal(event_id="X-1", session_id="S-1")
        self.assertEqual(signal.platform, "piaoniu")
        self.assertEqual(signal.signal_type, SignalType.ON_SALE)
        self.assertEqual(signal.price_tiers, ["380"])
        self.assertEqual(signal.official_purchase_url, "https://www.piaoniu.com/product/X-1")
        self.assertEqual(signal.metadata["source"], "official_api")


if __name__ == "__main__":
    unittest.main()
