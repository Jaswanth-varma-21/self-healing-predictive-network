from sklearn.ensemble import IsolationForest

from ml_features import prepare_ml_features


def train_isolation_forest(
    contamination="auto",
    random_state=42,
):
    _, features = prepare_ml_features()

    model = IsolationForest(
        contamination=contamination,
        random_state=random_state,
    )

    model.fit(features)

    return model


def detect_anomalies(model):
    _, features = prepare_ml_features()

    predictions = model.predict(features)
    scores = model.decision_function(features)

    results = features.copy()
    results["ml_prediction"] = predictions
    results["ml_anomaly"] = predictions == -1
    results["ml_score"] = scores

    return results
