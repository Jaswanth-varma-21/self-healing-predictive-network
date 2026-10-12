CAUSAL_FACTORS = {
    "LATENCY_INCREASE": {
        "description": "Increase in network round-trip latency",
        "features": [
            "rtt_avg_ms",
            "rtt_max_ms",
            "delta_rtt_avg_ms",
            "delta_rtt_max_ms",
        ],
    },
    "PACKET_LOSS": {
        "description": "Packet loss observed in network traffic",
        "features": [
            "packet_loss_percent",
            "delta_packet_loss_percent",
        ],
    },
    "RTT_VARIABILITY": {
        "description": "Variation in round-trip latency",
        "features": [
            "rtt_mdev_ms",
            "delta_rtt_mdev_ms",
        ],
    },
}


def get_causal_factor_names():
    return list(CAUSAL_FACTORS.keys())


def get_causal_factor(name):
    return CAUSAL_FACTORS.get(name)


if __name__ == "__main__":
    print("CAUSAL_FACTORS:", get_causal_factor_names())
    print("CAUSAL_FACTOR_MODULE: PASS")
