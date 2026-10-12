import json
import sqlite3
import os
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = Path(os.environ.get("CN_TELEMETRY_DB", PROJECT_ROOT / "telemetry" / "data" / "telemetry.db"))


def load_telemetry_data():
    conn = sqlite3.connect(DATABASE_PATH)

    query = """
        SELECT
            id,
            timestamp,
            source,
            node,
            port,
            metrics_json
        FROM telemetry
        ORDER BY timestamp, id
    """

    try:
        rows = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    if rows.empty:
        return rows

    def normalize_metrics(value):
        data = json.loads(value)
        if isinstance(data, dict) and isinstance(data.get("metrics"), dict):
            return data["metrics"]
        return data

    metrics = rows["metrics_json"].apply(normalize_metrics)
    metrics_df = pd.json_normalize(metrics)

    # The database 'port' column is authoritative.
    # Remove any duplicate 'port' field coming from metrics_json.
    if "port" in metrics_df.columns:
        metrics_df = metrics_df.drop(columns=["port"])

    dataset = pd.concat(
        [
            rows.drop(columns=["metrics_json"]).reset_index(drop=True),
            metrics_df.reset_index(drop=True)
        ],
        axis=1
    )

    return dataset


if __name__ == "__main__":
    dataset = load_telemetry_data()

    print("=== TELEMETRY DATASET ===")
    print("Rows:", len(dataset))
    print("Columns:", list(dataset.columns))
    print("Shape:", dataset.shape)
    print(dataset.to_string(index=False))
