import time

from sync_engine.network_status_sync import synchronize_network_status


def run_periodic_sync(network_state, iterations=3, interval=1.0):
    """
    Run controlled periodic Digital Twin synchronization.

    Parameters:
        network_state: Digital Twin network state.
        iterations: Number of synchronization cycles.
        interval: Delay between cycles in seconds.

    Returns:
        List of synchronization timestamps.
    """

    timestamps = []

    for _ in range(iterations):
        synchronize_network_status(network_state)
        timestamps.append(network_state["last_updated"])

        if len(timestamps) < iterations:
            time.sleep(interval)

    return timestamps
