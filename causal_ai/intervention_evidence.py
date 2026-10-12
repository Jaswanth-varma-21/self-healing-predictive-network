CONTROLLED_INTERVENTIONS = {
    "PACKET_LOSS": {
        "experiment": "Packet-loss injection",
        "mechanism": "netem loss 30%",
        "observed_feature": "packet_loss_percent",
        "evidence_strength": "controlled_intervention",
    },
    "LATENCY_INCREASE": {
        "experiment": "Latency injection",
        "mechanism": "netem delay 100ms",
        "observed_feature": "rtt_avg_ms",
        "evidence_strength": "controlled_intervention",
    },
    "PACKET_CORRUPTION": {
        "experiment": "Packet-corruption injection",
        "mechanism": "netem corrupt 30%",
        "observed_feature": "packet_loss_percent",
        "evidence_strength": "controlled_intervention",
    },
}


def get_intervention_evidence():
    return CONTROLLED_INTERVENTIONS


if __name__ == "__main__":
    print("INTERVENTION_COUNT:", len(CONTROLLED_INTERVENTIONS))
    print("INTERVENTION_EVIDENCE_MODULE: PASS")
