from counterfactual.outcome import evaluate_connectivity
from counterfactual.network_status import evaluate_network_status


def evaluate_counterfactual_outcome(
    counterfactual_state,
    scenario,
    source,
    destination,
):
    """
    Combine connectivity and network-status evaluation
    into one standardized counterfactual outcome.
    """

    connectivity = evaluate_connectivity(
        counterfactual_state,
        source,
        destination,
    )

    network_status = evaluate_network_status(
        counterfactual_state,
    )

    return {
        "scenario_id": scenario["scenario_id"],
        "action": scenario["action"],
        "source": source,
        "destination": destination,
        "reachable": connectivity["reachable"],
        "path_status": connectivity["path_status"],
        "network_status": network_status["network_status"],
        "links_operational": network_status["links_operational"],
        "links_total": network_status["links_total"],
    }
