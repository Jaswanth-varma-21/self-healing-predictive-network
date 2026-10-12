def detect_state_changes(previous_state, current_state):
    changes = {"nodes": [], "links": [], "network_status": None}

    for name, current in current_state.get("nodes", {}).items():
        previous = previous_state.get("nodes", {}).get(name, {})
        if previous.get("status") != current.get("status"):
            changes["nodes"].append({
                "node": name,
                "previous_status": previous.get("status"),
                "current_status": current.get("status")
            })

    for name, current in current_state.get("links", {}).items():
        previous = previous_state.get("links", {}).get(name, {})
        if previous.get("status") != current.get("status"):
            changes["links"].append({
                "link": name,
                "previous_status": previous.get("status"),
                "current_status": current.get("status")
            })

    previous_status = previous_state.get("network_status")
    current_status = current_state.get("network_status")

    if previous_status != current_status:
        changes["network_status"] = {
            "previous_status": previous_status,
            "current_status": current_status
        }

    return changes
