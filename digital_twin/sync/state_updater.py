from datetime import datetime


def update_node_state(network_state, node_name, node_type, status):
    if node_name not in network_state["nodes"]:
        raise ValueError(f"Unknown node: {node_name}")

    network_state["nodes"][node_name] = {
        "type": node_type,
        "status": status
    }

    network_state["last_updated"] = datetime.now().timestamp()

    return network_state


def update_link_state(network_state, source, destination, status):
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
