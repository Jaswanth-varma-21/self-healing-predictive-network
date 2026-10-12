import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "anomaly_detection" / "data"))

from telemetry_dataset import load_telemetry_data


def build_failure_dataset():
    dataset = load_telemetry_data()

    ping_data = (
        dataset[
            (dataset["source"] == "ping")
            & dataset["packet_loss_percent"].notna()
            & dataset["rtt_avg_ms"].notna()
        ]
        .sort_values(["timestamp", "id"])
        .copy()
    )

    ping_data["next_packet_loss"] = (
        ping_data["packet_loss_percent"].shift(-1)
    )

    ping_data["next_rtt_avg_ms"] = (
        ping_data["rtt_avg_ms"].shift(-1)
    )

    ping_data["next_failure"] = None

    valid_next = (
        ping_data["next_packet_loss"].notna()
        & ping_data["next_rtt_avg_ms"].notna()
    )

    ping_data.loc[valid_next, "next_failure"] = (
        (ping_data.loc[valid_next, "next_packet_loss"] > 0)
        | (ping_data.loc[valid_next, "next_rtt_avg_ms"] > 0.438)
    ).astype(int)

    prediction_dataset = ping_data[
        valid_next
    ].copy()

    return prediction_dataset


if __name__ == "__main__":
    data = build_failure_dataset()

    print("Failure prediction dataset")
    print("--------------------------")
    print("Rows:", len(data))
    print("Columns:", list(data.columns))
    print()
    print(
        data[
            [
                "id",
                "packet_loss_percent",
                "rtt_avg_ms",
                "rtt_max_ms",
                "rtt_mdev_ms",
                "next_packet_loss",
                "next_failure",
            ]
        ].to_string(index=False)
    )
