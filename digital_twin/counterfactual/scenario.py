def create_counterfactual_scenario(
    scenario_id,
    action,
    source,
    destination,
    status,
    description
):
    """
    Create a structured description of a hypothetical
    network change.
    """
    if not scenario_id:
        raise ValueError("scenario_id is required")

    if not action:
        raise ValueError("action is required")

    if not source:
        raise ValueError("source is required")

    if not destination:
        raise ValueError("destination is required")

    if status not in {"up", "down"}:
        raise ValueError("status must be 'up' or 'down'")

    return {
        "scenario_id": str(scenario_id),
        "action": str(action),
        "source": str(source),
        "destination": str(destination),
        "status": str(status),
        "description": str(description),
    }
