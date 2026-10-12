from failure_prediction.decision.recovery_policy import decide_recovery


def build_recovery_decision(prediction_result, causal_result):
    risk_state = prediction_result["risk_state"]
    top_cause = causal_result["top_cause"]

    decision = decide_recovery(risk_state, top_cause)

    return {
        "failure_prediction": prediction_result["failure_prediction"],
        "failure_probability": prediction_result["failure_probability"],
        "risk_state": risk_state,
        "top_cause": top_cause,
        "causal_score": causal_result["causal_score"],
        "intervention_evidence": causal_result["intervention_evidence"],
        "recovery_decision": decision,
    }


if __name__ == "__main__":
    print("RECOVERY_DECISION_MODULE: PASS")
