from causal_ai.factors.cause_scorer import (
    score_causal_factors,
    rank_causal_factors,
)
from causal_ai.intervention_evidence import (
    get_intervention_evidence,
)


def analyze_causal_evidence(features):
    scores = score_causal_factors(features)
    ranked = rank_causal_factors(scores)
    interventions = get_intervention_evidence()

    evidence = []

    for factor, score in ranked:
        intervention = interventions.get(factor)

        evidence.append({
            "factor": factor,
            "score": score,
            "intervention_evidence": (
                intervention is not None
            ),
            "evidence_strength": (
                intervention["evidence_strength"]
                if intervention
                else "telemetry_only"
            ),
        })

    return evidence


if __name__ == "__main__":
    print("CAUSAL_EVIDENCE_MODULE: PASS")
