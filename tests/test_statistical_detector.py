import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT / "anomaly_detection" / "data"))
sys.path.insert(0, str(PROJECT_ROOT / "anomaly_detection" / "baseline"))
sys.path.insert(0, str(PROJECT_ROOT / "anomaly_detection" / "detectors"))

from baseline_statistics import calculate_baseline
from statistical_detector import DETECTION_METRICS, detect_statistical_anomalies


class TestStatisticalDetector(unittest.TestCase):
    def test_zero_standard_deviation_does_not_flag_anomaly(self):
        dataset = pd.DataFrame({
            "source": ["test"] * 3,
            "node": ["switch1"] * 3,
            "port": ["1"] * 3,
            "timestamp": [100.0, 105.0, 110.0],
            "id": [1, 2, 3],
            "rx_packets": [100, 110, 120],
            "rx_bytes": [1000, 1100, 1200],
            "rx_dropped": [0, 0, 0],
            "rx_errors": [0, 0, 0],
            "tx_packets": [200, 210, 220],
            "tx_bytes": [2000, 2100, 2200],
            "tx_dropped": [0, 0, 0],
            "tx_errors": [0, 0, 0],
        })

        baseline = calculate_baseline(dataset)
        results = detect_statistical_anomalies(dataset, baseline)

        eligible = results[results["state"] == "normal"]

        self.assertEqual(len(eligible), 2)
        self.assertFalse(eligible["anomaly"].any())
        self.assertTrue(eligible["max_abs_zscore"].isna().all())

        for metric in DETECTION_METRICS:
            self.assertTrue(
                eligible[f"{metric}_zscore"].isna().all()
            )


    def test_large_counter_spike_is_detected(self):
        baseline_data = pd.DataFrame({
            "source": ["test"] * 5,
            "node": ["switch1"] * 5,
            "port": ["1"] * 5,
            "timestamp": [100.0, 105.0, 110.0, 115.0, 120.0],
            "id": [1, 2, 3, 4, 5],
            "rx_packets": [100, 110, 121, 130, 140],
            "rx_bytes": [1000, 1100, 1210, 1300, 1400],
            "rx_dropped": [0, 0, 0, 0, 0],
            "rx_errors": [0, 0, 0, 0, 0],
            "tx_packets": [200, 210, 221, 230, 240],
            "tx_bytes": [2000, 2100, 2210, 2300, 2400],
            "tx_dropped": [0, 0, 0, 0, 0],
            "tx_errors": [0, 0, 0, 0, 0],
        })

        test_data = pd.DataFrame({
            "source": ["test"] * 4,
            "node": ["switch1"] * 4,
            "port": ["1"] * 4,
            "timestamp": [200.0, 205.0, 210.0, 215.0],
            "id": [6, 7, 8, 9],
            "rx_packets": [100, 110, 120, 1120],
            "rx_bytes": [1000, 1100, 1200, 11200],
            "rx_dropped": [0, 0, 0, 0],
            "rx_errors": [0, 0, 0, 0],
            "tx_packets": [200, 210, 220, 1220],
            "tx_bytes": [2000, 2100, 2200, 12200],
            "tx_dropped": [0, 0, 0, 0],
            "tx_errors": [0, 0, 0, 0],
        })

        baseline = calculate_baseline(baseline_data)
        results = detect_statistical_anomalies(test_data, baseline)

        spike = results.loc[results["id"] == 9].iloc[0]

        self.assertTrue(bool(spike["anomaly"]))
        self.assertGreaterEqual(spike["max_abs_zscore"], 3.0)


    def test_long_sampling_gap_is_not_scored(self):
        dataset = pd.DataFrame({
            "source": ["test"] * 3,
            "node": ["switch1"] * 3,
            "port": ["1"] * 3,
            "timestamp": [100.0, 105.0, 125.0],
            "id": [1, 2, 3],
            "rx_packets": [100, 110, 10000],
            "rx_bytes": [1000, 1100, 100000],
            "rx_dropped": [0, 0, 0],
            "rx_errors": [0, 0, 0],
            "tx_packets": [200, 210, 10000],
            "tx_bytes": [2000, 2100, 100000],
            "tx_dropped": [0, 0, 0],
            "tx_errors": [0, 0, 0],
        })

        baseline = calculate_baseline(dataset)
        results = detect_statistical_anomalies(dataset, baseline)

        gap_row = results.loc[results["id"] == 3].iloc[0]

        self.assertEqual(gap_row["state"], "long_gap")
        self.assertFalse(bool(gap_row["anomaly"]))
        self.assertTrue(np.isnan(gap_row["max_abs_zscore"]))

        for metric in DETECTION_METRICS:
            self.assertTrue(np.isnan(gap_row[f"{metric}_zscore"]))


    def test_counter_reset_is_not_scored(self):
        dataset = pd.DataFrame({
            "source": ["test"] * 3,
            "node": ["switch1"] * 3,
            "port": ["1"] * 3,
            "timestamp": [100.0, 105.0, 110.0],
            "id": [1, 2, 3],
            "rx_packets": [100, 110, 5],
            "rx_bytes": [1000, 1100, 50],
            "rx_dropped": [0, 0, 0],
            "rx_errors": [0, 0, 0],
            "tx_packets": [200, 210, 5],
            "tx_bytes": [2000, 2100, 50],
            "tx_dropped": [0, 0, 0],
            "tx_errors": [0, 0, 0],
        })

        baseline = calculate_baseline(dataset)
        results = detect_statistical_anomalies(dataset, baseline)

        reset_row = results.loc[results["id"] == 3].iloc[0]

        self.assertEqual(reset_row["state"], "counter_reset")
        self.assertFalse(bool(reset_row["anomaly"]))
        self.assertTrue(np.isnan(reset_row["max_abs_zscore"]))

        for metric in DETECTION_METRICS:
            self.assertTrue(np.isnan(reset_row[f"{metric}_zscore"]))


if __name__ == "__main__":
    unittest.main()
