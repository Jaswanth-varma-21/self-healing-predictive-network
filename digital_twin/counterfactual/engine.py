from counterfactual.counterfactual_state import (
    create_counterfactual_state,
    apply_counterfactual_link_change,
)


def simulate_counterfactual(network_state, scenario):
    """
    Create an isolated counterfactual state and apply
    the requested hypothetical scenario.
    """
    counterfactual_state = create_counterfactual_state(network_state)

    if scenario["action"] == "LINK_FAILURE":
        apply_counterfactual_link_change(
            counterfactual_state,
            scenario["source"],
            scenario["destination"],
            scenario["status"],
        )
    else:
        raise ValueError(
            f"Unsupported counterfactual action: {scenario['action']}"
        )

    return counterfactual_state
