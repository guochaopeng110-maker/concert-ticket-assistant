import unittest

from concert_ticket_assistant.platforms.damai.adapter import DamaiAdapter
from concert_ticket_assistant.platforms.factory import build_platform_adapter
from concert_ticket_assistant.platforms.maoyan.adapter import MaoyanAdapter


class PlatformFactoryTests(unittest.TestCase):
    def test_build_supported_platforms(self) -> None:
        self.assertIsInstance(build_platform_adapter("damai"), DamaiAdapter)
        self.assertIsInstance(build_platform_adapter("maoyan"), MaoyanAdapter)

    def test_build_unsupported_platform_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_platform_adapter("unknown")


if __name__ == "__main__":
    unittest.main()

