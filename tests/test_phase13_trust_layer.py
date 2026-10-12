import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from security import trust_layer as trust


class TestTrustLayer(unittest.TestCase):
    def test_route_must_be_discovered_and_loop_free(self):
        graph = {1: {2: 3}, 2: {1: 1, 3: 2}, 3: {2: 1}}
        self.assertEqual(trust.validate_path([1, 2, 3], graph), (True, "accepted"))
        self.assertFalse(trust.validate_path([1, 3], graph)[0])
        self.assertFalse(trust.validate_path([1, 2, 1], graph)[0])
        self.assertFalse(trust.validate_path([1, 2, 3], graph, [(2, 3)])[0])

    def test_telemetry_rejects_nonfinite_and_implausible_values(self):
        self.assertFalse(trust.validate_telemetry_metrics({"rtt_avg_ms": math.nan})[0])
        self.assertFalse(trust.validate_telemetry_metrics({"packet_loss_percent": 101})[0])
        self.assertFalse(trust.validate_telemetry_metrics({"rtt_avg_ms": -1})[0])
        self.assertTrue(trust.validate_telemetry_metrics({"rtt_avg_ms": 1.2, "packet_loss_percent": 0})[0])

    def test_stale_telemetry_is_rejected_when_freshness_is_required(self):
        self.assertFalse(trust.validate_telemetry_metrics(
            {"packet_loss_percent": 0}, timestamp=10, now=100, max_age_seconds=20
        )[0])

    def test_module_authentication_is_constant_time_token_match(self):
        self.assertTrue(trust.authenticate_module("abc", "abc"))
        self.assertFalse(trust.authenticate_module("abc", "xyz"))
        self.assertFalse(trust.authenticate_module("", "abc"))
        self.assertFalse(trust.authenticate_module("abc", None))

    def test_reroute_requires_feasibility_and_path(self):
        graph = {"a": {"b": 1}, "b": {"a": 1, "c": 1}, "c": {"b": 1}}
        no_feasibility = {"recovery_action": "REROUTE_TRAFFIC", "counterfactual_feasible": False, "path": ["a", "b", "c"]}
        self.assertFalse(trust.validate_recovery_recommendation(no_feasibility, topology=graph)[0])
        feasible = {"recovery_action": "REROUTE_TRAFFIC", "counterfactual_feasible": True, "path": ["a", "b", "c"]}
        self.assertTrue(trust.validate_recovery_recommendation(feasible, topology=graph)[0])
        self.assertFalse(trust.validate_recovery_recommendation(feasible, role="observer", topology=graph)[0])
        self.assertFalse(trust.validate_recovery_recommendation({"action": "EXECUTE_ARBITRARY_COMMAND"})[0])

    def test_audit_event_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "audit.jsonl"
            with patch.object(trust, "AUDIT_LOG_PATH", target):
                record = trust.audit_event("unit_test", "approved", action="NO_ACTION")
            saved = json.loads(target.read_text().strip())
            self.assertEqual(saved["event"], "unit_test")
            self.assertEqual(saved["outcome"], "approved")
            self.assertEqual(record["details"]["action"], "NO_ACTION")


if __name__ == "__main__":
    unittest.main()
