import sys
from pathlib import Path
import numpy as np

_ANOMALY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ANOMALY_ROOT / "data"))
sys.path.insert(0, str(_ANOMALY_ROOT / "baseline"))

from telemetry_dataset import load_telemetry_data
from counter_preprocessor import prepare_counter_deltas
from baseline_statistics import calculate_baseline

DETECTION_METRICS = [
    "rx_packets_delta",
    "rx_bytes_delta",
    "tx_packets_delta",
    "tx_bytes_delta",
]

Z_THRESHOLD = 3.0

def detect_statistical_anomalies(dataset, baseline):
    processed = prepare_counter_deltas(dataset).copy()

    for metric in DETECTION_METRICS:
        processed[f"{metric}_zscore"] = np.nan

    processed["anomaly"] = False
    processed["max_abs_zscore"] = np.nan

    # Only score normal samples collected within the configured 10-second interval.
    for index, row in processed.iterrows():
        if row["state"] != "normal" or row["interval_seconds"] > 10.0:
            continue

        group_key = (row["source"], row["node"], row["port"])

        if group_key not in baseline.index:
            continue

        zscores = []

        for metric in DETECTION_METRICS:
            value = row[metric]
            mean = baseline.loc[group_key, (metric, "mean")]
            std = baseline.loc[group_key, (metric, "std")]

            if np.isfinite(std) and std > 0 and np.isfinite(value):
                zscore = (value - mean) / std
                processed.at[index, f"{metric}_zscore"] = zscore
                zscores.append(abs(zscore))

        if zscores:
            max_zscore = max(zscores)
            processed.at[index, "max_abs_zscore"] = max_zscore
            processed.at[index, "anomaly"] = (
                max_zscore >= Z_THRESHOLD
            )

    return processed

if __name__ == "__main__":
    dataset = load_telemetry_data()
    baseline = calculate_baseline(dataset)

    results = detect_statistical_anomalies(
        dataset,
        baseline
    )

    print("=== STATISTICAL ANOMALY DETECTOR ===")
    print("Z-score threshold:", Z_THRESHOLD)
    print("Rows analysed:", len(results))
    print("Anomalies detected:", int(results["anomaly"].sum()))
