import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from security import trust_layer
from telemetry.pipeline import telemetry_pipeline


class TestTelemetryIngressGuard(unittest.TestCase):
    def test_invalid_telemetry_rejected_before_database_write(self):
        with tempfile.TemporaryDirectory() as temp:
            audit = Path(temp) / "audit.jsonl"
            with patch.object(trust_layer, "AUDIT_LOG_PATH", audit):
                with self.assertRaises(ValueError):
                    telemetry_pipeline.store_telemetry(
                        "ping", "h1", None, {"packet_loss_percent": 101}
                    )
            self.assertTrue(audit.exists())
            self.assertIn("rejected", audit.read_text())


if __name__ == "__main__":
    unittest.main()
