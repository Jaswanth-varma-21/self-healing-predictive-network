import numpy as np
from telemetry_dataset import load_telemetry_data

COUNTER_COLUMNS = [
    "rx_packets",
    "rx_bytes",
    "rx_dropped",
    "rx_errors",
    "tx_packets",
    "tx_bytes",
    "tx_dropped",
    "tx_errors",
]

GAP_THRESHOLD_SECONDS = 10.0


def prepare_counter_deltas(dataset):
    required = {
        "source", "node", "port", "timestamp", "id",
        *COUNTER_COLUMNS,
    }
    missing = required.difference(dataset.columns)
    if missing:
        raise ValueError(
            f"Telemetry dataset is missing required columns: "
            f"{sorted(missing)}"
        )

    active = dataset[
        dataset["port"].astype(str) != "LOCAL"
    ].copy()

    group_columns = ["source", "node", "port"]

    active = active.sort_values(
        group_columns + ["timestamp", "id"]
    ).reset_index(drop=True)

    grouped = active.groupby(
        group_columns, dropna=False, sort=False
    )

    active["interval_seconds"] = grouped["timestamp"].diff()

    for column in COUNTER_COLUMNS:
        previous = grouped[column].shift(1)
        active[f"{column}_delta"] = active[column] - previous

    previous_rx = grouped["rx_packets"].shift(1)

    delta_columns = [
        f"{column}_delta" for column in COUNTER_COLUMNS
    ]

    reset_condition = active[delta_columns].lt(0).any(axis=1)
    initial_condition = previous_rx.isna()

    active["is_long_gap"] = (
        active["interval_seconds"] > GAP_THRESHOLD_SECONDS
    ).fillna(False)

    active["is_counter_reset"] = reset_condition
    active["is_initial"] = initial_condition

    active["state"] = np.select(
        [
            active["is_initial"],
            active["is_counter_reset"],
            active["is_long_gap"],
        ],
        [
            "initial",
            "counter_reset",
            "long_gap",
        ],
        default="normal",
    )

    # A reset invalidates the entire counter-delta vector.
    # Preserve the original counter values for future inspection.
    active.loc[reset_condition, delta_columns] = np.nan

    return active


if __name__ == "__main__":
    dataset = load_telemetry_data()
    processed = prepare_counter_deltas(dataset)

    print("=== COUNTER PREPROCESSOR ===")
    print("Input rows:", len(dataset))
    print("Active-port rows:", len(processed))
    print("\nState counts:")
    print(processed["state"].value_counts(dropna=False))

    print("\nSampling gaps:")
    print(processed["is_long_gap"].value_counts())

    print("\nCounter resets:")
    print(processed["is_counter_reset"].sum())

    print("\nNegative deltas after reset handling:")
    delta_columns = [
        f"{column}_delta" for column in COUNTER_COLUMNS
    ]
    print(
        int(
            (
                processed[delta_columns]
                .lt(0)
                .any(axis=1)
            ).sum()
        )
    )
