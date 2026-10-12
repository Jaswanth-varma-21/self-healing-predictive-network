def evaluate_recovery_feasibility(recovery_action, counterfactual_outcome):
    """
    Determine whether a proposed recovery action is feasible
    according to the simulated counterfactual outcome.
    """

    recovery_action = str(recovery_action)

    reachable = bool(counterfactual_outcome.get("reachable", False))

    if recovery_action == "REROUTE_TRAFFIC":
        if reachable:
            return {
                "recovery_action": recovery_action,
                "feasible": True,
                "status": "FEASIBLE",
                "reason": "The destination remains reachable in the simulated topology.",
            }

        return {
            "recovery_action": recovery_action,
            "feasible": False,
            "status": "NOT_FEASIBLE",
            "reason": "No operational path to the destination exists in the simulated topology.",
        }

    if recovery_action == "INCREASE_MONITORING":
        return {
            "recovery_action": recovery_action,
            "feasible": True,
            "status": "MONITOR_ONLY",
            "reason": "The action does not modify network forwarding.",
        }

    if recovery_action == "NONE":
        return {
            "recovery_action": recovery_action,
            "feasible": True,
            "status": "NOT_APPLICABLE",
            "reason": "No automatic recovery action is requested.",
        }

    return {
        "recovery_action": recovery_action,
        "feasible": False,
        "status": "UNKNOWN_ACTION",
        "reason": "The recovery action is not supported by the counterfactual evaluator.",
    }
