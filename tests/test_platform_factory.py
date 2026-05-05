import unittest

from concert_ticket_assistant.platforms.damai.adapter import DamaiAdapter
from concert_ticket_assistant.platforms.factory import (
    build_platform_adapter,
    ensure_default_platforms_registered,
    list_platforms,
)
from concert_ticket_assistant.platforms.maoyan.adapter import MaoyanAdapter
from concert_ticket_assistant.platforms.registry import (
    build_registered_platform,
    clear_registry,
    register_platform,
)


class PlatformFactoryTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_registry()
        # Reset bootstrap flag by re-importing function context behavior through direct call chain.
        # ensure_default_platforms_registered is idempotent and used in each test path.
        import concert_ticket_assistant.platforms.factory as factory_module

        factory_module._BOOTSTRAPPED = False

    def test_build_supported_platforms(self) -> None:
        self.assertIsInstance(build_platform_adapter("damai"), DamaiAdapter)
        self.assertIsInstance(build_platform_adapter("maoyan"), MaoyanAdapter)

    def test_list_platforms(self) -> None:
        ensure_default_platforms_registered()
        self.assertEqual(list_platforms(), ["damai", "maoyan"])

    def test_build_unsupported_platform_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_platform_adapter("unknown")

    def test_dynamic_registration(self) -> None:
        class DummyAdapter:
            name = "dummy"

        register_platform("dummy", DummyAdapter)
        adapter = build_registered_platform("dummy")
        self.assertEqual(adapter.name, "dummy")

    def test_duplicate_registration_rejected(self) -> None:
        class DummyAdapter:
            name = "dummy"

        register_platform("dummy", DummyAdapter)
        with self.assertRaises(ValueError):
            register_platform("dummy", DummyAdapter)


if __name__ == "__main__":
    unittest.main()

