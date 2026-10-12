from datetime import datetime


def create_anomaly_event(
    record_id,
    node,
    target,
    anomaly_type,
    severity,
    packet_loss_percent,
    threshold_anomaly,
    ml_anomaly,
):
    return {
        "event_id": f"ANOMALY-{record_id}",
        "record_id": record_id,
        "timestamp": datetime.now().timestamp(),
        "node": node,
        "target": target,
        "anomaly_type": anomaly_type,
        "severity": severity,
        "packet_loss_percent": packet_loss_percent,
        "threshold_anomaly": bool(threshold_anomaly),
        "ml_anomaly": bool(ml_anomaly),
    }
