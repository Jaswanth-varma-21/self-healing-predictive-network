PACKET_LOSS_THRESHOLD = 0.0


def detect_packet_loss_anomaly(packet_loss_percent):
    return packet_loss_percent > PACKET_LOSS_THRESHOLD


RTT_AVG_THRESHOLD_MS = 0.438


def detect_rtt_anomaly(rtt_avg_ms):
    return rtt_avg_ms > RTT_AVG_THRESHOLD_MS


def detect_threshold_anomalies(packet_loss_percent, rtt_avg_ms):
    packet_loss_anomaly = detect_packet_loss_anomaly(
        packet_loss_percent
    )

    rtt_anomaly = detect_rtt_anomaly(
        rtt_avg_ms
    )

    return {
        "packet_loss_anomaly": packet_loss_anomaly,
        "rtt_anomaly": rtt_anomaly,
        "anomaly": (
            packet_loss_anomaly
            or rtt_anomaly
        ),
    }
