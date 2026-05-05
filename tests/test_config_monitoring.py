import json
import tempfile
import unittest
from pathlib import Path

from concert_ticket_assistant.core.config import MonitorConfig, load_config
from concert_ticket_assistant.core.monitoring import RunMetrics, save_error_snapshot


class ConfigTests(unittest.TestCase):
    def test_load_config_json_file(self) -> None:
        payload = {"event_id": "E1", "session_id": "S1", "price_tier": "480"}
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as fp:
            fp.write(json.dumps(payload))
            fp.flush()
            path = fp.name
        data = load_config(path)
        Path(path).unlink(missing_ok=True)
        self.assertEqual(data["event_id"], "E1")
        cfg = MonitorConfig.from_dict(data)
        self.assertEqual(cfg.session_id, "S1")


class MonitoringTests(unittest.TestCase):
    def test_breaker_opens_on_consecutive_failures(self) -> None:
        metrics = RunMetrics()
        metrics.on_adapter_error("network_error")
        metrics.on_adapter_error("network_error")
        opened = metrics.maybe_open_breaker(fail_threshold=2, cooldown_seconds=5, now=10.0)
        self.assertTrue(opened)
        self.assertTrue(metrics.breaker_open(now=12.0))
        self.assertFalse(metrics.breaker_open(now=16.0))

    def test_save_error_snapshot_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = save_error_snapshot(
                base_dir=tmp,
                platform="damai",
                kind="parse_error",
                cycle=3,
                event_id="E1",
                session_id="S1",
                payload="raw-body",
            )
            file = Path(path)
            self.assertTrue(file.exists())
            self.assertIn("raw-body", file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
