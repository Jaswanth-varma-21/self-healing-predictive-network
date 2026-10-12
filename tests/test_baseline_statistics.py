import sys
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT / "anomaly_detection" / "data"))
sys.path.insert(0, str(PROJECT_ROOT / "anomaly_detection" / "baseline"))

from baseline_statistics import calculate_baseline


class TestBaselineStatistics(unittest.TestCase):
    def test_baseline_calculates_mean_and_count(self):
        dataset = pd.DataFrame({
            "source": ["test"] * 3,
            "node": ["switch1"] * 3,
            "port": ["1"] * 3,
            "timestamp": [100.0, 105.0, 110.0],
            "id": [1, 2, 3],
            "rx_packets": [100, 110, 130],
            "rx_bytes": [1000, 1100, 1300],
            "rx_dropped": [0, 0, 0],
            "rx_errors": [0, 0, 0],
            "tx_packets": [200, 220, 250],
            "tx_bytes": [2000, 2200, 2500],
            "tx_dropped": [0, 0, 0],
            "tx_errors": [0, 0, 0],
        })

        baseline = calculate_baseline(dataset)
        group_key = ("test", "switch1", "1")

        self.assertIn(group_key, baseline.index)

        rx_packets_count = baseline.loc[
            group_key, ("rx_packets_delta", "count")
        ]
        rx_packets_mean = baseline.loc[
            group_key, ("rx_packets_delta", "mean")
        ]

        self.assertEqual(rx_packets_count, 2)
        self.assertAlmostEqual(rx_packets_mean, 15.0)


if __name__ == "__main__":
    unittest.main()
