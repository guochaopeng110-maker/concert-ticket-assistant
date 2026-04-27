import unittest
from unittest.mock import MagicMock

from concert_ticket_assistant.core.models import SignalType
from concert_ticket_assistant.platforms.damai.adapter import DamaiAdapter, DamaiAdapterError


class DamaiAdapterTests(unittest.TestCase):
    def test_parse_payload_supports_jsonp_wrapper(self) -> None:
        payload = '__jp0({"perform":{"performId":"100"},"skuPagePcBuyBtn":{"skuBtnList":[]}})'
        parsed = DamaiAdapter._parse_subpage_payload(payload)
        self.assertEqual(parsed["perform"]["performId"], "100")

    def test_parse_payload_rejects_invalid_json(self) -> None:
        with self.assertRaises(DamaiAdapterError):
            DamaiAdapter._parse_subpage_payload("__jp0({invalid})")

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
        response.text = (
            '__jp0({"perform":{"performId":"S-1","skuList":[{"priceName":"480"}],'
            '"x":"x"},"skuPagePcBuyBtn":{"skuBtnList":[{"btnText":"选座购买"}]}})'
        )
        response.raise_for_status.return_value = None
        session.get.return_value = response

        adapter = DamaiAdapter(session=session)
        signal = adapter.poll_signal(event_id="E-1", session_id="S-1")
        self.assertEqual(signal.signal_type, SignalType.ON_SALE)
        self.assertEqual(signal.price_tiers, ["480"])
        self.assertEqual(signal.metadata["perform_id"], "S-1")


if __name__ == "__main__":
    unittest.main()

