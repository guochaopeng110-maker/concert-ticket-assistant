import unittest
from pathlib import Path
from unittest.mock import MagicMock

from concert_ticket_assistant.core.models import SignalType
from concert_ticket_assistant.platforms.damai.adapter import (
    DamaiAdapter,
    DamaiAdapterError,
    DamaiErrorKind,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "damai"


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class DamaiAdapterTests(unittest.TestCase):
    def test_parse_payload_supports_jsonp_wrapper(self) -> None:
        parsed = DamaiAdapter._parse_subpage_payload(_fixture("subpage_on_sale.jsonp"))
        self.assertEqual(parsed["perform"]["performId"], "S-1")

    def test_parse_payload_classification_matrix(self) -> None:
        cases = [
            ("subpage_login.html", DamaiErrorKind.NOT_LOGGED_IN),
            ("subpage_risk.html", DamaiErrorKind.RISK_CONTROL),
            ("subpage_api_changed.html", DamaiErrorKind.API_CHANGED),
            ("subpage_temp_busy.txt", DamaiErrorKind.TEMPORARY_UNAVAILABLE),
            ("subpage_missing_fields.json", DamaiErrorKind.API_CHANGED),
        ]
        for filename, expected in cases:
            with self.assertRaises(DamaiAdapterError) as ctx:
                DamaiAdapter._parse_subpage_payload(_fixture(filename))
            self.assertEqual(ctx.exception.kind, expected, filename)

    def test_parse_payload_invalid_json_is_parse_error(self) -> None:
        with self.assertRaises(DamaiAdapterError) as ctx:
            DamaiAdapter._parse_subpage_payload("__jp0({invalid})")
        self.assertEqual(ctx.exception.kind, DamaiErrorKind.PARSE_ERROR)

    def test_build_signal_detects_on_sale_tiers(self) -> None:
        adapter = DamaiAdapter()
        payload = {
            "perform": {"skuList": [{"priceName": "480"}, {"priceName": "680"}]},
            "skuPagePcBuyBtn": {"skuBtnList": [{"btnText": "立即购买"}, {"btnText": "即将开抢"}]},
        }
        signal, tiers = adapter._build_signal(payload)
        self.assertEqual(signal, SignalType.ON_SALE)
        self.assertEqual(tiers, ["480"])

    def test_poll_signal_maps_response(self) -> None:
        session = MagicMock()
        response = MagicMock()
        response.text = _fixture("subpage_on_sale.jsonp")
        response.raise_for_status.return_value = None
        session.get.return_value = response

        adapter = DamaiAdapter(session=session)
        signal = adapter.poll_signal(event_id="E-1", session_id="S-1")
        self.assertEqual(signal.signal_type, SignalType.ON_SALE)
        self.assertEqual(signal.price_tiers, ["480"])
        self.assertEqual(signal.metadata["perform_id"], "S-1")


if __name__ == "__main__":
    unittest.main()

