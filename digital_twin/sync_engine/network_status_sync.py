from datetime import datetime


def synchronize_network_status(network_state):
    """
    Derive the overall Digital Twin network status
    from current node and link states.
    """

    all_nodes_up = all(
        node["status"] == "up"
        for node in network_state["nodes"].values()
    )

    all_links_up = all(
        link["status"] == "up"
        for link in network_state["links"].values()
    )

    if all_nodes_up and all_links_up:
        network_state["network_status"] = "operational"
    else:
        network_state["network_status"] = "degraded"

    network_state["last_updated"] = datetime.now().timestamp()

    return network_state
