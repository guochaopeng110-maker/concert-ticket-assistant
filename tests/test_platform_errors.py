import unittest

from concert_ticket_assistant.platforms.errors import AdapterError, AdapterErrorKind


class PlatformErrorsTests(unittest.TestCase):
    def test_adapter_error_contract(self) -> None:
        err = AdapterError("x", AdapterErrorKind.PARSE_ERROR, raw_payload="raw")
        self.assertEqual(str(err), "x")
        self.assertEqual(err.kind, "parse_error")
        self.assertEqual(err.raw_payload, "raw")


if __name__ == "__main__":
    unittest.main()

