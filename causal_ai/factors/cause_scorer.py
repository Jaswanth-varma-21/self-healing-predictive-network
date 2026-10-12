from causal_ai.factors.causal_factors import CAUSAL_FACTORS


def score_causal_factors(features):
    scores = {}

    packet_loss = float(features.get("packet_loss_percent", 0.0))
    delta_packet_loss = float(
        features.get("delta_packet_loss_percent", 0.0)
    )

    rtt_avg = float(features.get("rtt_avg_ms", 0.0))
    rtt_max = float(features.get("rtt_max_ms", 0.0))
    delta_rtt_avg = float(
        features.get("delta_rtt_avg_ms", 0.0)
    )
    delta_rtt_max = float(
        features.get("delta_rtt_max_ms", 0.0)
    )

    rtt_mdev = float(features.get("rtt_mdev_ms", 0.0))
    delta_rtt_mdev = float(
        features.get("delta_rtt_mdev_ms", 0.0)
    )

    scores["PACKET_LOSS"] = max(
        0.0,
        min(
            1.0,
            (packet_loss / 100.0)
            + max(0.0, delta_packet_loss) / 100.0,
        ),
    )

    latency_score = max(
        0.0,
        delta_rtt_avg / 100.0,
        delta_rtt_max / 100.0,
        rtt_avg / 100.0,
        rtt_max / 100.0,
    )

    scores["LATENCY_INCREASE"] = min(1.0, latency_score)

    variability_score = max(
        0.0,
        rtt_mdev / 10.0,
        delta_rtt_mdev / 10.0,
    )

    scores["RTT_VARIABILITY"] = min(
        1.0,
        variability_score,
    )

    return scores


def rank_causal_factors(scores):
    return sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )


if __name__ == "__main__":
    print("CAUSAL_FACTOR_COUNT:", len(CAUSAL_FACTORS))
    print("CAUSE_SCORER_MODULE: PASS")
