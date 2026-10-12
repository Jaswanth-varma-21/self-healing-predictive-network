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

DEFAULT_THRESHOLD = 0.60


def build_weighted_logistic_model():
    return Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(
            class_weight="balanced",
            random_state=42,
            max_iter=1000,
        )),
    ])


def predict_failure(model, features, threshold=DEFAULT_THRESHOLD):
    probability = float(model.predict_proba(features)[0, 1])
    prediction = int(probability >= threshold)
    return prediction, probability


if __name__ == "__main__":
    print("Weighted Logistic prediction model module loaded.")
    print("FEATURE_COUNT:", len(FEATURES))
    print("DEFAULT_THRESHOLD:", DEFAULT_THRESHOLD)
    print("CLASS_WEIGHT: balanced")
