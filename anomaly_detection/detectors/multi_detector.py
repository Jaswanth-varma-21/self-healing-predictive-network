def combine_detector_results(
    threshold_anomaly,
    ml_anomaly,
    required_votes=2,
):
    votes = int(threshold_anomaly) + int(ml_anomaly)

    return {
        "threshold_anomaly": bool(threshold_anomaly),
        "ml_anomaly": bool(ml_anomaly),
        "anomaly_votes": votes,
        "required_votes": required_votes,
        "overall_anomaly": votes >= required_votes,
    }
