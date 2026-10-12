import sqlite3
import time
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = Path(os.environ.get("CN_TELEMETRY_DB", PROJECT_ROOT / "telemetry" / "data" / "telemetry.db"))


def store_prediction(
    source,
    node,
    probability,
    prediction,
    risk_state,
    timestamp=None,
):
    if timestamp is None:
        timestamp = time.time()

    probability = float(probability)
    prediction = int(prediction)

    if not 0.0 <= probability <= 1.0:
        raise ValueError("Probability must be between 0.0 and 1.0")

    if prediction not in (0, 1):
        raise ValueError("Prediction must be 0 or 1")

    conn = sqlite3.connect(DATABASE_PATH)

    cursor = conn.execute(
        """
        INSERT INTO prediction_results
        (timestamp, source, node, probability, prediction, risk_state)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp,
            str(source),
            str(node),
            probability,
            prediction,
            str(risk_state),
        ),
    )

    conn.commit()
    prediction_id = cursor.lastrowid
    conn.close()

    return prediction_id


if __name__ == "__main__":
    print("PREDICTION_STORAGE_MODULE: PASS")
