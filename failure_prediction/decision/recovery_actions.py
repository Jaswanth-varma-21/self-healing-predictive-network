RECOVERY_ACTIONS = {
    "NO_ACTION": {
        "action": "NONE",
        "description": "Continue normal network operation and monitoring.",
    },
    "MONITOR": {
        "action": "INCREASE_MONITORING",
        "description": "Continue monitoring without changing network forwarding.",
    },
    "RECOVER_PACKET_LOSS": {
        "action": "REROUTE_TRAFFIC",
        "description": "Prepare traffic rerouting away from the degraded path.",
    },
    "RECOVER_LATENCY": {
        "action": "REROUTE_TRAFFIC",
        "description": "Prepare traffic rerouting away from the high-latency path.",
    },
    "RECOVER_VARIABILITY": {
        "action": "REROUTE_TRAFFIC",
        "description": "Prepare traffic rerouting away from the unstable path.",
    },
    "SAFE_FALLBACK": {
        "action": "NONE",
        "description": "Do not make an automatic network change because the cause is uncertain.",
    },
}


def get_recovery_action(decision):
    return RECOVERY_ACTIONS.get(decision, RECOVERY_ACTIONS["SAFE_FALLBACK"])


if __name__ == "__main__":
    print("RECOVERY_ACTIONS_MODULE: PASS")
