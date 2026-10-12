def validate_twin_structure(twin_data):
    required_sections = {
        "topology",
        "nodes",
        "links",
        "state"
    }

    missing_sections = required_sections - set(twin_data.keys())

    if missing_sections:
        raise ValueError(
            f"Missing Digital Twin sections: {sorted(missing_sections)}"
        )

    return True
