import tempfile
import unittest
from pathlib import Path

from concert_ticket_assistant.tools.platform_scaffold import normalize_platform_name, scaffold_platform


class PlatformScaffoldTests(unittest.TestCase):
    def test_normalize_platform_name(self) -> None:
        self.assertEqual(normalize_platform_name(" Piao-Niu V2 "), "piao_niu_v2")
        with self.assertRaises(ValueError):
            normalize_platform_name("___")

    def test_scaffold_generates_adapter_fixture_and_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            created = scaffold_platform(root, "piaoniu")
            created_set = {str(path.relative_to(root)).replace("\\", "/") for path in created}
            self.assertIn("concert_ticket_assistant/platforms/piaoniu/adapter.py", created_set)
            self.assertIn("concert_ticket_assistant/platforms/piaoniu/__init__.py", created_set)
            self.assertIn("tests/test_piaoniu_adapter.py", created_set)
            self.assertIn("tests/fixtures/piaoniu/payload_on_sale.json", created_set)
            self.assertIn("tests/fixtures/piaoniu/payload_login.html", created_set)
            self.assertIn("tests/fixtures/piaoniu/payload_busy.json", created_set)
            self.assertIn("tests/fixtures/piaoniu/payload_missing_fields.json", created_set)
            adapter_text = (root / "concert_ticket_assistant/platforms/piaoniu/adapter.py").read_text(encoding="utf-8")
            self.assertIn("class PiaoniuAdapter", adapter_text)
            self.assertIn('name: str = "piaoniu"', adapter_text)

    def test_scaffold_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scaffold_platform(root, "piaoniu")
            with self.assertRaises(FileExistsError):
                scaffold_platform(root, "piaoniu")


if __name__ == "__main__":
    unittest.main()

