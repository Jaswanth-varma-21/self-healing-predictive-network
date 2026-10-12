TOPOLOGY_METADATA = {
    "name": "mininet_single_switch",
    "environment": "Mininet",
    "topology_type": "single_switch",
}

TOPOLOGY = {
    "nodes": {
        "h1": {
            "type": "host"
        },
        "s1": {
            "type": "switch"
        },
        "h2": {
            "type": "host"
        }
    },
    "links": [
        {
            "source": "h1",
            "destination": "s1"
        },
        {
            "source": "s1",
            "destination": "h2"
        }
    ]
}
