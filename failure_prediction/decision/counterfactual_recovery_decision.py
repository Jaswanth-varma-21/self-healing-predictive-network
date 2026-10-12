from failure_prediction.decision.recovery_policy import (
    DECISION_SAFE_FALLBACK,
)
from failure_prediction.decision.recovery_actions import (
    get_recovery_action,
)
from counterfactual.recovery_feasibility import (
    evaluate_recovery_feasibility,
)


def build_counterfactual_recovery_decision(
    recommendation,
    counterfactual_outcome,
):
    """
    Validate a proposed recovery action against the
    counterfactual Digital Twin before execution.
    """

    proposed_action = recommendation["recovery_action"]

    feasibility = evaluate_recovery_feasibility(
        proposed_action,
        counterfactual_outcome,
    )

    if feasibility["feasible"]:
        return {
            **recommendation,
            "counterfactual_status": feasibility["status"],
            "counterfactual_feasible": True,
            "counterfactual_reason": feasibility["reason"],
        }

    fallback_action = get_recovery_action(
        DECISION_SAFE_FALLBACK
    )

    return {
        **recommendation,
        "recovery_decision": DECISION_SAFE_FALLBACK,
        "recovery_action": fallback_action["action"],
        "action_description": fallback_action["description"],
        "counterfactual_status": feasibility["status"],
        "counterfactual_feasible": False,
        "counterfactual_reason": feasibility["reason"],
    }
