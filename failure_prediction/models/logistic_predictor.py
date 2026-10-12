import sys

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


FEATURES = [
    "packet_loss_percent",
    "rtt_avg_ms",
    "rtt_max_ms",
    "rtt_mdev_ms",
    "delta_packet_loss_percent",
    "delta_rtt_avg_ms",
    "delta_rtt_max_ms",
    "delta_rtt_mdev_ms",
]


def build_logistic_model():
    return Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(
            random_state=42,
            max_iter=1000,
        )),
    ])


if __name__ == "__main__":
    print("Logistic prediction model module loaded.")
    print("FEATURE_COUNT:", len(FEATURES))
    print("FEATURES:", FEATURES)
    print("MODEL:", build_logistic_model())
