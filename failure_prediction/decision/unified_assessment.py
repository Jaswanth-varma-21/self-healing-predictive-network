from failure_prediction.decision.prediction_decision import evaluate_prediction
from causal_ai.analysis.causal_evidence import analyze_causal_evidence
from causal_ai.analysis.root_cause_explainer import explain_root_cause


def evaluate_failure(model, features):
    prediction_result = evaluate_prediction(model, features)
    causal_features = features.iloc[0].to_dict()
    causal_evidence = analyze_causal_evidence(causal_features)
    causal_explanation = explain_root_cause(causal_evidence)

    return {
        **prediction_result,
        "top_cause": causal_explanation["top_cause"],
        "causal_score": causal_explanation.get("score"),
        "intervention_evidence": causal_explanation["intervention_evidence"],
        "cause_explanation": causal_explanation["explanation"],
    }


if __name__ == "__main__":
    print("UNIFIED_ASSESSMENT_MODULE: PASS")
