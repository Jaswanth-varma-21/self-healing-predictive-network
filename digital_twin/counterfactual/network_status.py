def evaluate_network_status(counterfactual_state):
    """
    Evaluate the overall network status using the same
    operational/degraded terminology as the existing
    Digital Twin.
    """

    nodes = counterfactual_state.get("nodes", {})
    links = counterfactual_state.get("links", {})

    node_statuses = [
        node.get("status")
        for node in nodes.values()
    ]

    link_statuses = [
        link.get("status")
        for link in links.values()
    ]

    if all(status == "up" for status in node_statuses + link_statuses):
        network_status = "operational"
    else:
        network_status = "degraded"

    return {
        "network_status": network_status,
        "nodes_operational": sum(
            status == "up" for status in node_statuses
        ),
        "nodes_total": len(node_statuses),
        "links_operational": sum(
            status == "up" for status in link_statuses
        ),
        "links_total": len(link_statuses),
    }
