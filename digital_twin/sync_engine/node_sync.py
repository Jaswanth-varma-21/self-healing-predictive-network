from datetime import datetime


def synchronize_node_state(network_state, node_name, node_type, status):
    """
    Synchronize the observed physical node state
    into the Digital Twin network state.
    """

    if node_name not in network_state["nodes"]:
        raise ValueError(f"Unknown node: {node_name}")

    network_state["nodes"][node_name] = {
        "type": node_type,
        "status": status
    }

    network_state["last_updated"] = datetime.now().timestamp()

    return network_state
