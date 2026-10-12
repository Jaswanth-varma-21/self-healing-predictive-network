from datetime import datetime


def synchronize_link_state(
    network_state,
    source,
    destination,
    status
):
    """
    Synchronize the observed physical link state
    into the Digital Twin network state.
    """

    key = f"{source}->{destination}"

    if key not in network_state["links"]:
        raise ValueError(f"Unknown link: {key}")

    network_state["links"][key] = {
        "source": source,
        "destination": destination,
        "status": status
    }

    network_state["last_updated"] = datetime.now().timestamp()

    return network_state
