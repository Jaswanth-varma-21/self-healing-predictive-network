NORMAL_THRESHOLD = 0.30
HIGH_RISK_THRESHOLD = 0.60


def classify_failure_risk(probability):
    probability = float(probability)

    if not 0.0 <= probability <= 1.0:
        raise ValueError("Probability must be between 0.0 and 1.0")

    if probability < NORMAL_THRESHOLD:
        return "NORMAL"
    elif probability < HIGH_RISK_THRESHOLD:
        return "WARNING"
    else:
        return "HIGH_RISK"


if __name__ == "__main__":
    test_probabilities = [0.10, 0.30, 0.59, 0.60, 0.90]

    for probability in test_probabilities:
        print(
            "PROBABILITY:",
            probability,
            "RISK:",
            classify_failure_risk(probability),
        )

    print("RISK_CLASSIFIER_MODULE: PASS")
