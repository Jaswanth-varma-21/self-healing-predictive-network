import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "data"))

from prediction_features import build_prediction_features


MIN_SAMPLES_PER_CLASS = 5


def check_prediction_readiness(data):
    class_counts = data["next_failure"].value_counts().to_dict()

    normal_count = int(class_counts.get(0, 0))
    failure_count = int(class_counts.get(1, 0))

    ready = (
        normal_count >= MIN_SAMPLES_PER_CLASS
        and failure_count >= MIN_SAMPLES_PER_CLASS
    )

    return {
        "total_samples": len(data),
        "normal_samples": normal_count,
        "failure_samples": failure_count,
        "minimum_samples_per_class": MIN_SAMPLES_PER_CLASS,
        "ready_for_supervised_training": ready,
    }


if __name__ == "__main__":
    data = build_prediction_features()
    result = check_prediction_readiness(data)

    print("Failure prediction readiness")
    print("----------------------------")

    for key, value in result.items():
        print(f"{key}: {value}")
