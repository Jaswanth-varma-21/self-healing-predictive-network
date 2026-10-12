from datetime import datetime


def record_update_timestamp(network_state):
    """
    Record the current synchronization timestamp
    in the Digital Twin network state.
    """

    network_state["last_updated"] = datetime.now().timestamp()

    return network_state


def get_last_update_timestamp(network_state):
    """
    Return the most recent Digital Twin update timestamp.
    """

    return network_state.get("last_updated")
