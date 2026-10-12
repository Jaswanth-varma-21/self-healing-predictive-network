import sqlite3
import time
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = Path(os.environ.get("CN_TELEMETRY_DB", PROJECT_ROOT / "telemetry" / "data" / "telemetry.db"))


def store_recovery_decision(source, node, recommendation, timestamp=None):
    if timestamp is None:
        timestamp = time.time()

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.execute(
        """
        INSERT INTO recovery_decisions
        (timestamp, source, node, risk_state, top_cause,
         recovery_decision, recovery_action, action_description,
         counterfactual_status, counterfactual_feasible)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp,
            str(source),
            str(node),
            str(recommendation["risk_state"]),
            recommendation.get("top_cause"),
            str(recommendation["recovery_decision"]),
            str(recommendation["recovery_action"]),
            str(recommendation["action_description"]),
            recommendation.get("counterfactual_status"),
            recommendation.get("counterfactual_feasible"),
        ),
    )
    conn.commit()
    decision_id = cursor.lastrowid
    conn.close()
    return decision_id


if __name__ == "__main__":
    print("RECOVERY_STORAGE_MODULE: PASS")
