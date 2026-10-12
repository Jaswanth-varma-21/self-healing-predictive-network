def map_node_state(node_name, node_type, status):
    return {
        "name": node_name,
        "type": node_type,
        "status": status
    }


def map_link_state(source, destination, status):
    return {
        "source": source,
        "destination": destination,
        "status": status
    }
