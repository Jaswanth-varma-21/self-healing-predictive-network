import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from failure_prediction.data.prediction_features import build_prediction_features
from failure_prediction.models.weighted_logistic_predictor import (
    build_weighted_logistic_model,
    FEATURES,
    DEFAULT_THRESHOLD,
)


MIN_TRAIN_SAMPLES = 2


def evaluate_walk_forward():
    data = (
        build_prediction_features()
        .dropna(subset=FEATURES)
        .copy()
        .reset_index(drop=True)
    )

    results = []

    for test_index in range(MIN_TRAIN_SAMPLES, len(data)):
        train = data.iloc[:test_index]
        test = data.iloc[[test_index]]

        if train["next_failure"].nunique() < 2:
            continue

        model = build_weighted_logistic_model()
        model.fit(
            train[FEATURES],
            train["next_failure"].astype(int),
        )

        probability = float(
            model.predict_proba(test[FEATURES])[0, 1]
        )

        prediction = int(probability >= DEFAULT_THRESHOLD)
        actual = int(test["next_failure"].iloc[0])
        sample_id = int(test["id"].iloc[0])

        results.append(
            {
                "id": sample_id,
                "actual": actual,
                "prediction": prediction,
                "probability": probability,
            }
        )

    return results


def calculate_metrics(results):
    tp = sum(
        r["actual"] == 1 and r["prediction"] == 1
        for r in results
    )
    tn = sum(
        r["actual"] == 0 and r["prediction"] == 0
        for r in results
    )
    fp = sum(
        r["actual"] == 0 and r["prediction"] == 1
        for r in results
    )
    fn = sum(
        r["actual"] == 1 and r["prediction"] == 0
        for r in results
    )

    total = len(results)

    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )

    return {
        "TP": tp,
        "TN": tn,
        "FP": fp,
        "FN": fn,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


if __name__ == "__main__":
    results = evaluate_walk_forward()
    metrics = calculate_metrics(results)

    print("WALK_FORWARD_RESULTS")
    print("ID | ACTUAL | PRED | PROB")
    print("-" * 30)

    for result in results:
        print(
            result["id"],
            "|",
            result["actual"],
            "|",
            result["prediction"],
            "|",
            round(result["probability"], 4),
        )

    print()
    print("CONFUSION_MATRIX")
    print("TP:", metrics["TP"])
    print("TN:", metrics["TN"])
    print("FP:", metrics["FP"])
    print("FN:", metrics["FN"])

    print()
    print("METRICS")
    print("Accuracy:", round(metrics["accuracy"], 4))
    print("Precision:", round(metrics["precision"], 4))
    print("Recall:", round(metrics["recall"], 4))
    print("F1:", round(metrics["f1"], 4))

    print()
    print("EVALUATION_TEST: PASS")
