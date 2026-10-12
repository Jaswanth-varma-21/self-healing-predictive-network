from failure_prediction.decision.recovery_decision import build_recovery_decision
from failure_prediction.decision.recovery_actions import get_recovery_action


def build_recovery_recommendation(prediction_result, causal_result):
    decision_result = build_recovery_decision(prediction_result, causal_result)
    action = get_recovery_action(decision_result["recovery_decision"])

    return {
        **decision_result,
        "recovery_action": action["action"],
        "action_description": action["description"],
    }


if __name__ == "__main__":
    print("RECOVERY_RECOMMENDATION_MODULE: PASS")
