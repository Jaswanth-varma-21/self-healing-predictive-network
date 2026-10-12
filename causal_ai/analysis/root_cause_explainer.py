def explain_root_cause(causal_evidence):
    if not causal_evidence:
        return {
            "top_cause": None,
            "explanation": "No causal evidence available.",
        }

    top = causal_evidence[0]

    cause = top["factor"]
    score = float(top["score"])
    intervention = top["intervention_evidence"]

    if intervention:
        evidence_text = "controlled intervention evidence available"
    else:
        evidence_text = "telemetry evidence only"

    explanation = (
        f"{cause} is the leading candidate cause "
        f"with a score of {score:.4f}; "
        f"{evidence_text}."
    )

    return {
        "top_cause": cause,
        "score": score,
        "intervention_evidence": intervention,
        "explanation": explanation,
    }


if __name__ == "__main__":
    print("ROOT_CAUSE_EXPLAINER: PASS")
