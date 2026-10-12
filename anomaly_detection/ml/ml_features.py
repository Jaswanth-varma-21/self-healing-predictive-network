import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))

from telemetry_dataset import load_telemetry_data


ML_FEATURES = [
    "packet_loss_percent",
    "rtt_avg_ms",
    "rtt_max_ms",
    "rtt_mdev_ms",
]


def prepare_ml_features():
    dataset = load_telemetry_data()

    ping_data = dataset[
        dataset["source"] == "ping"
    ].copy()

    features = ping_data[ML_FEATURES].copy()

    return ping_data, features
