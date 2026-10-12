"""Verified-outcome feedback storage for Phase 12."""

import json
import sqlite3
import time
from pathlib import Path
from contextlib import closing

DATABASE_PATH = (
    Path(__file__).resolve().parents[1]
    / "telemetry" / "data" / "telemetry.db"
)


def initialize_feedback_store():
    with closing(sqlite3.connect(DATABASE_PATH)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS learning_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                node TEXT NOT NULL,
                features_json TEXT NOT NULL,
                predicted_failure INTEGER
                    CHECK (predicted_failure IN (0, 1)),
                verified_failure INTEGER NOT NULL
                    CHECK (verified_failure IN (0, 1)),
                verification_source TEXT NOT NULL,
                notes TEXT
            )
        """)
        conn.commit()


def record_verified_outcome(
    node, features, verified_failure, verification_source,
    predicted_failure=None, notes=None
):
    if type(verified_failure) is not int or verified_failure not in (0, 1):
        raise ValueError("verified_failure must be integer 0 or 1")

    if predicted_failure is not None and (
        type(predicted_failure) is not int or predicted_failure not in (0, 1)
    ):
        raise ValueError("predicted_failure must be None, 0, or 1")

    if not isinstance(features, dict) or not features:
        raise ValueError("features must be a non-empty dictionary")

    if not isinstance(node, str) or not node.strip():
        raise ValueError("node must be a non-empty string")

    if not isinstance(verification_source, str) or not verification_source.strip():
        raise ValueError("verification_source must be provided")

    features_json = json.dumps(features, allow_nan=False)
    initialize_feedback_store()

    with closing(sqlite3.connect(DATABASE_PATH)) as conn:
        cursor = conn.execute("""
            INSERT INTO learning_feedback (
                timestamp, node, features_json, predicted_failure,
                verified_failure, verification_source, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            time.time(), node.strip(), features_json, predicted_failure,
            verified_failure, verification_source.strip(), notes
        ))
        conn.commit()
        return cursor.lastrowid


def get_feedback_count():
    initialize_feedback_store()
    with closing(sqlite3.connect(DATABASE_PATH)) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM learning_feedback"
        ).fetchone()[0]


if __name__ == "__main__":
    initialize_feedback_store()
    print("Feedback store initialized.")
    print("Database:", DATABASE_PATH)
    print("Verified feedback records:", get_feedback_count())
