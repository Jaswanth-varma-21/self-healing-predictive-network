"""Guarded candidate-training preparation for Phase 12.

This module does not promote or replace the live prediction model.
Only explicitly approved verification sources may contribute feedback.
"""

import json
import sqlite3
from pathlib import Path
from contextlib import closing

from failure_prediction.models.weighted_logistic_predictor import (
    FEATURES,
    build_weighted_logistic_model,
)

DATABASE_PATH = (
    Path(__file__).resolve().parents[1]
    / "telemetry" / "data" / "telemetry.db"
)

MIN_SAMPLES_PER_CLASS = 5

# Add a source only after confirming that it represents independently
# verified real network outcomes. Synthetic test sources are never allowed.
APPROVED_VERIFICATION_SOURCES = frozenset()


def load_eligible_feedback():
    if not DATABASE_PATH.exists():
        return []

    with closing(sqlite3.connect(DATABASE_PATH)) as conn:
        rows = conn.execute("""
            SELECT id, timestamp, node, features_json,
                   verified_failure, verification_source
            FROM learning_feedback
            ORDER BY timestamp, id
        """).fetchall()

    eligible = []
    for row in rows:
        record_id, timestamp, node, features_json, label, source = row

        if source not in APPROVED_VERIFICATION_SOURCES:
            continue

        try:
            features = json.loads(features_json)
        except (TypeError, json.JSONDecodeError):
            continue

        if not isinstance(features, dict):
            continue

        if not all(
            feature in features
            and isinstance(features[feature], (int, float))
            and not isinstance(features[feature], bool)
        for feature in FEATURES):
            continue

        eligible.append({
            "id": record_id,
            "timestamp": timestamp,
            "node": node,
            "features": features,
            "label": int(label),
            "verification_source": source,
        })

    return eligible


def check_training_readiness(records):
    counts = {
        0: sum(record["label"] == 0 for record in records),
        1: sum(record["label"] == 1 for record in records),
    }
    ready = all(
        counts[label] >= MIN_SAMPLES_PER_CLASS
        for label in (0, 1)
    )
    return {
        "eligible_samples": len(records),
        "normal_samples": counts[0],
        "failure_samples": counts[1],
        "minimum_per_class": MIN_SAMPLES_PER_CLASS,
        "ready_for_training": ready,
    }


def train_candidate(records):
    """Train an in-memory candidate only when basic data checks pass."""
    readiness = check_training_readiness(records)
    if not readiness["ready_for_training"]:
        raise ValueError(
            f"Insufficient eligible verified feedback: {readiness}"
        )

    records = sorted(
        records, key=lambda record: (record["timestamp"], record["id"])
    )
    import pandas as pd

    features = pd.DataFrame(
        [record["features"] for record in records],
        columns=FEATURES,
    )
    labels = [record["label"] for record in records]

    model = build_weighted_logistic_model()
    model.fit(features, labels)
    return model


if __name__ == "__main__":
    records = load_eligible_feedback()
    print("Phase 12 candidate-training readiness")
    print("-------------------------------------")
    for key, value in check_training_readiness(records).items():
        print(f"{key}: {value}")
    print("Live model changed: False")
