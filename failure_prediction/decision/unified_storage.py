from failure_prediction.decision.prediction_storage import store_prediction
from failure_prediction.decision.causal_storage import store_causal_assessment


def store_unified_assessment(source, node, prediction_result, causal_result, timestamp=None):
    prediction_id = store_prediction(
        source=source,
        node=node,
        probability=prediction_result["failure_probability"],
        prediction=prediction_result["failure_prediction"],
        risk_state=prediction_result["risk_state"],
        timestamp=timestamp,
    )

    causal_id = store_causal_assessment(
        source=source,
        node=node,
        top_cause=causal_result["top_cause"],
        causal_score=causal_result["causal_score"],
        intervention_evidence=causal_result["intervention_evidence"],
        explanation=causal_result["cause_explanation"],
        timestamp=timestamp,
    )

    return {
        "prediction_id": prediction_id,
        "causal_id": causal_id,
    }


if __name__ == "__main__":
    print("UNIFIED_STORAGE_MODULE: PASS")
