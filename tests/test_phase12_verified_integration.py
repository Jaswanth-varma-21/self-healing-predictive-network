import json
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from failure_prediction.models.weighted_logistic_predictor import FEATURES
from failure_prediction import continuous_learning
from failure_prediction.verified_outcome_integration import record_experiment_outcome


class TestPhase12VerifiedIntegration(unittest.TestCase):
    def test_evidence_referenced_outcome_is_stored_without_approving_source(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "feedback.db"
            features = {key: 0.0 for key in FEATURES}
            with patch.object(continuous_learning, "DATABASE_PATH", db):
                row_id = record_experiment_outcome(
                    node="test-switch",
                    measured_features=features,
                    verified_failure=0,
                    verification_source="unit_test_only",
                    evidence_reference="test://independent-evidence",
                )
                with closing(sqlite3.connect(db)) as conn:
                    row = conn.execute(
                        "SELECT node, features_json, verified_failure, notes FROM learning_feedback WHERE id=?",
                        (row_id,),
                    ).fetchone()
            self.assertEqual(row[0], "test-switch")
            self.assertEqual(json.loads(row[1]), features)
            self.assertEqual(row[2], 0)
            self.assertIn("evidence_reference=test://independent-evidence", row[3])

    def test_missing_feature_or_evidence_rejected(self):
        with self.assertRaises(ValueError):
            record_experiment_outcome("h1", {}, 0, "source", "evidence")
        with self.assertRaises(ValueError):
            record_experiment_outcome("h1", {key: 0.0 for key in FEATURES}, 0, "source", "")


if __name__ == "__main__":
    unittest.main()
