import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))

from telemetry_dataset import load_telemetry_data
from counter_preprocessor import prepare_counter_deltas


BASELINE_METRICS = [
    "rx_packets_delta",
    "rx_bytes_delta",
    "tx_packets_delta",
    "tx_bytes_delta",
]


def calculate_baseline(dataset):
    processed = prepare_counter_deltas(dataset)

    normal = processed[
        (processed["state"] == "normal")
        & (processed["interval_seconds"] <= 10.0)
    ].copy()

    baseline = (
        normal
        .groupby(["source", "node", "port"], dropna=False)[BASELINE_METRICS]
        .agg(["count", "mean", "std", "min", "max"])
    )

    return baseline


if __name__ == "__main__":
    dataset = load_telemetry_data()
    baseline = calculate_baseline(dataset)

    print("=== NORMAL NETWORK BASELINE ===")
    print(baseline.round(3).to_string())
