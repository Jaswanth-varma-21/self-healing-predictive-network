import sqlite3
import time
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = Path(os.environ.get("CN_TELEMETRY_DB", PROJECT_ROOT / "telemetry" / "data" / "telemetry.db"))


def store_causal_assessment(source, node, top_cause, causal_score, intervention_evidence, explanation, timestamp=None):
    if timestamp is None:
        timestamp = time.time()

    causal_score = float(causal_score)
    intervention_evidence = int(bool(intervention_evidence))

    if not 0.0 <= causal_score <= 1.0:
        raise ValueError("causal_score must be between 0 and 1")

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.execute("INSERT INTO causal_assessments (timestamp, source, node, top_cause, causal_score, intervention_evidence, explanation) VALUES (?, ?, ?, ?, ?, ?, ?)", (timestamp, str(source), str(node), top_cause, causal_score, intervention_evidence, str(explanation)))
    conn.commit()
    assessment_id = cursor.lastrowid
    conn.close()
    return assessment_id


if __name__ == "__main__":
    print("CAUSAL_STORAGE_MODULE: PASS")
