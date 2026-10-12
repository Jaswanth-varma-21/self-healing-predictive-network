RISK_NORMAL = "NORMAL"
RISK_WARNING = "WARNING"
RISK_HIGH = "HIGH_RISK"

DECISION_NO_ACTION = "NO_ACTION"
DECISION_MONITOR = "MONITOR"
DECISION_RECOVER_PACKET_LOSS = "RECOVER_PACKET_LOSS"
DECISION_RECOVER_LATENCY = "RECOVER_LATENCY"
DECISION_RECOVER_VARIABILITY = "RECOVER_VARIABILITY"
DECISION_SAFE_FALLBACK = "SAFE_FALLBACK"


def decide_recovery(risk_state, top_cause):
    risk_state = str(risk_state)
    top_cause = str(top_cause) if top_cause is not None else ""

    if risk_state == RISK_NORMAL:
        return DECISION_NO_ACTION

    if risk_state == RISK_WARNING:
        return DECISION_MONITOR

    if risk_state == RISK_HIGH:
        if top_cause == "PACKET_LOSS":
            return DECISION_RECOVER_PACKET_LOSS
        if top_cause == "LATENCY_INCREASE":
            return DECISION_RECOVER_LATENCY
        if top_cause == "RTT_VARIABILITY":
            return DECISION_RECOVER_VARIABILITY
        return DECISION_SAFE_FALLBACK

    return DECISION_SAFE_FALLBACK


if __name__ == "__main__":
    print("RECOVERY_POLICY_MODULE: PASS")
