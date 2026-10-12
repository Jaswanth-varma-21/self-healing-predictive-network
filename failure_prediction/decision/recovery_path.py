DEFAULT_SOURCE = "h1"
DEFAULT_DESTINATION = "h2"

DEFAULT_PATH = [
    ("h1", "s1"),
    ("s1", "h2"),
]


def get_default_recovery_path():
    return list(DEFAULT_PATH)


def get_primary_link(source=DEFAULT_SOURCE):
    path = get_default_recovery_path()

    for link_source, link_destination in path:
        if link_source == source:
            return {
                "source": link_source,
                "destination": link_destination,
            }

    raise ValueError(
        f"No primary recovery link found for source: {source}"
    )


if __name__ == "__main__":
    print("RECOVERY_PATH_MODULE: PASS")
