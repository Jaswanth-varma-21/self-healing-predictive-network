import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "data"))

from prediction_features import build_prediction_features


def predict_failure_baseline(data):
    return (data["packet_loss_percent"] > 0).astype(int)


if __name__ == "__main__":
    data = build_prediction_features()
    data["baseline_prediction"] = predict_failure_baseline(data)

    print("Failure prediction baseline")
    print("---------------------------")
    print(
        data[
            [
                "id",
                "packet_loss_percent",
                "next_failure",
                "baseline_prediction",
            ]
        ].to_string(index=False)
    )
