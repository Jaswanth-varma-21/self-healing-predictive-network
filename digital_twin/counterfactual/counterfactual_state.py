import copy


def create_counterfactual_state(network_state):
    """
    Create an isolated counterfactual copy of the current
    Digital Twin network state.
    """
    return copy.deepcopy(network_state)


def apply_counterfactual_link_change(
    counterfactual_state,
    source,
    destination,
    status
):
    """
    Apply a hypothetical link-state change only to the
    counterfactual state.
    """
    key = f"{source}->{destination}"

    if key not in counterfactual_state.get("links", {}):
        raise ValueError(f"Unknown link: {key}")

    counterfactual_state["links"][key] = {
        "source": source,
        "destination": destination,
        "status": status
    }

    return counterfactual_state


def verify_original_state_unchanged(original_state, counterfactual_state):
    """
    Verify that the counterfactual state is independent
    from the original Digital Twin state.
    """
    if original_state == counterfactual_state:
        return False

    return True
