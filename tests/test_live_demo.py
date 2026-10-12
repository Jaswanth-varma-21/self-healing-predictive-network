import unittest
from unittest.mock import patch

from demo import live_demo


class TestLiveDemoScenarios(unittest.TestCase):
    def test_scenario_controls_are_simulation_only(self):
        with patch.object(live_demo, "get_status", return_value={"simulation": {"scenario": "congestion"}}):
            result = live_demo.set_scenario("congestion")
        self.assertEqual(result["simulation"]["scenario"], "congestion")
        self.assertIn("congestion", live_demo.SIMULATION_SCENARIOS)
        self.assertIn("recovery_failure", live_demo.SIMULATION_SCENARIOS)

    def test_unknown_scenario_is_rejected(self):
        with self.assertRaises(ValueError):
            live_demo.set_scenario("execute_shell_command")

    def test_database_path_discovers_project_database_when_env_is_stale(self):
        from pathlib import Path
        with patch.dict("os.environ", {"CN_TELEMETRY_DB": "/definitely/missing/telemetry.db"}):
            resolved = live_demo.resolve_database_path()
        self.assertTrue(resolved.is_file())
        self.assertEqual(resolved.name, "telemetry.db")

    def test_simulation_scenarios_have_distinct_metrics(self):
        normal = live_demo.SIMULATION_SCENARIOS["normal"]
        congestion = live_demo.SIMULATION_SCENARIOS["congestion"]
        self.assertNotEqual(normal["packet_loss_percent"], congestion["packet_loss_percent"])
        self.assertNotEqual(normal["latency_ms"], congestion["latency_ms"])


if __name__ == "__main__":
    unittest.main()
