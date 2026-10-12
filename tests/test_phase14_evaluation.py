import tempfile
import unittest
from pathlib import Path

from evaluation.framework import (
    binary_classification_metrics, evaluate_records, numeric_summary, write_report
)


class TestPhase14Evaluation(unittest.TestCase):
    def test_classification_metrics(self):
        rows = [
            {"actual_failure": 1, "predicted_failure": 1},
            {"actual_failure": 0, "predicted_failure": 0},
            {"actual_failure": 0, "predicted_failure": 1},
            {"actual_failure": 1, "predicted_failure": 0},
        ]
        result = binary_classification_metrics(rows)
        self.assertEqual((result["TP"], result["TN"], result["FP"], result["FN"]), (1, 1, 1, 1))
        self.assertEqual(result["accuracy"], 0.5)
        self.assertEqual(result["f1"], 0.5)

    def test_baseline_and_proposed_are_compared_only_when_both_present(self):
        rows = [
            {"system": "baseline", "actual_failure": 1, "predicted_failure": 0, "recovery_time_ms": 100},
            {"system": "proposed", "actual_failure": 1, "predicted_failure": 1, "recovery_time_ms": 50},
        ]
        result = evaluate_records(rows)
        self.assertEqual(result["by_system"]["baseline"]["classification"]["recall"], 0.0)
        self.assertEqual(result["by_system"]["proposed"]["classification"]["recall"], 1.0)
        self.assertEqual(result["proposed_minus_baseline"]["recovery_time_ms"], -50.0)
        self.assertEqual(result["proposed_minus_baseline"]["recall"], 1.0)

    def test_unmeasured_values_are_not_invented(self):
        result = evaluate_records([{"scenario": "no-labels", "recovery_time_ms": ""}])
        self.assertIsNone(result["classification"])
        self.assertIsNone(result["recovery_time_ms"]["mean"])
        self.assertEqual(result["recovery_time_ms"]["count"], 0)

    def test_report_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as temp:
            result = evaluate_records([{"actual_failure": 0, "predicted_failure": 0, "packet_loss_percent": 0}])
            json_path, md_path = write_report(result, temp)
            self.assertTrue(json_path.exists() and md_path.exists())
            self.assertIn("unavailable", md_path.read_text())


if __name__ == "__main__":
    unittest.main()
