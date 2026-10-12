import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from failure_dataset import build_failure_dataset


CURRENT_FEATURES = [
    "packet_loss_percent",
    "rtt_avg_ms",
    "rtt_max_ms",
    "rtt_mdev_ms",
]

DELTA_FEATURES = [
    "delta_packet_loss_percent",
    "delta_rtt_avg_ms",
    "delta_rtt_max_ms",
    "delta_rtt_mdev_ms",
]


def build_prediction_features():
    dataset = build_failure_dataset().copy()

    for feature in CURRENT_FEATURES:
        delta_feature = "delta_" + feature
        dataset.loc[:, delta_feature] = dataset[feature].diff()

    return dataset


if __name__ == "__main__":
    data = build_prediction_features()

    print("Prediction feature dataset")
    print("--------------------------")
    print("Rows:", len(data))
    print("Delta features:", DELTA_FEATURES)
    print()
    print(
        data[
            ["id"] + CURRENT_FEATURES + DELTA_FEATURES + ["next_failure"]
        ].to_string(index=False)
    )
