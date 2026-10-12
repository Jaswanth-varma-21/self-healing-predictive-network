from models.node import NODE_MODEL
from models.link import LINK_MODEL


def create_initial_network_state():
    state = {
        "network_status": "operational",
        "nodes": {},
        "links": {},
        "last_updated": None
    }

    for name, node in NODE_MODEL.items():
        state["nodes"][name] = {
            "type": node["type"],
            "status": node["status"]
        }

    for link in LINK_MODEL:
        key = f"{link['source']}->{link['destination']}"

        state["links"][key] = {
            "source": link["source"],
            "destination": link["destination"],
            "status": link["status"]
        }

    return state


NETWORK_STATE = create_initial_network_state()
