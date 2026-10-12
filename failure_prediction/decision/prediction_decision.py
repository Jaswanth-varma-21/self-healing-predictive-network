from failure_prediction.models.weighted_logistic_predictor import (
    predict_failure,
    DEFAULT_THRESHOLD,
)
from failure_prediction.decision.risk_classifier import classify_failure_risk


def evaluate_prediction(model, features):
    prediction, probability = predict_failure(
        model,
        features,
        DEFAULT_THRESHOLD,
    )

    risk = classify_failure_risk(probability)

    return {
        "failure_prediction": prediction,
        "failure_probability": probability,
        "risk_state": risk,
    }


if __name__ == "__main__":
    print("PREDICTION_DECISION_MODULE: PASS")
