def classify_severity(
    threshold_anomaly,
    ml_anomaly,
):
    votes = int(threshold_anomaly) + int(ml_anomaly)

    if votes == 0:
        return "NORMAL"

    if votes == 1:
        return "WARNING"

    return "CRITICAL"
