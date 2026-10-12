from collections import deque


def evaluate_connectivity(counterfactual_state, source, destination):
    """
    Evaluate whether a source node can reach a destination node
    using links that are operational in the counterfactual state.
    """

    nodes = counterfactual_state.get("nodes", {})
    links = counterfactual_state.get("links", {})

    if source not in nodes:
        raise ValueError(f"Unknown source node: {source}")

    if destination not in nodes:
        raise ValueError(f"Unknown destination node: {destination}")

    adjacency = {node: [] for node in nodes}

    for link in links.values():
        if link.get("status") != "up":
            continue

        link_source = link["source"]
        link_destination = link["destination"]

        adjacency.setdefault(link_source, []).append(link_destination)
        adjacency.setdefault(link_destination, []).append(link_source)

    queue = deque([source])
    visited = {source}

    while queue:
        current = queue.popleft()

        if current == destination:
            return {
                "reachable": True,
                "source": source,
                "destination": destination,
                "path_status": "available",
            }

        for neighbor in adjacency.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return {
        "reachable": False,
        "source": source,
        "destination": destination,
        "path_status": "broken",
    }
