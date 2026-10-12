import sys
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "anomaly_detection" / "data"

sys.path.insert(0, str(DATA_DIR))

from counter_preprocessor import (
    COUNTER_COLUMNS,
    prepare_counter_deltas,
)


class TestCounterPreprocessor(unittest.TestCase):

    def make_dataset(self):
        rows = []

        for record_id, timestamp, packets, byte_count in [
            (1, 1000.0, 100, 1000),
            (2, 1005.0, 150, 1600),
        ]:
            row = {
                "id": record_id,
                "source": "ovs",
                "node": "s1",
                "port": "1",
                "timestamp": timestamp,
            }

            for column in COUNTER_COLUMNS:
                row[column] = 0

            row["rx_packets"] = packets
            row["rx_bytes"] = byte_count

            rows.append(row)

        return pd.DataFrame(rows)

    def test_counter_deltas_for_normal_increment(self):
        dataset = self.make_dataset()

        processed = prepare_counter_deltas(dataset)
        first = processed.iloc[0]
        second = processed.iloc[1]

        self.assertEqual(first["state"], "initial")
        self.assertTrue(pd.isna(first["rx_packets_delta"]))

        self.assertEqual(second["state"], "normal")
        self.assertEqual(second["interval_seconds"], 5.0)
        self.assertEqual(second["rx_packets_delta"], 50)
        self.assertEqual(second["rx_bytes_delta"], 600)


    def test_counter_reset_invalidates_all_deltas(self):
        dataset = self.make_dataset()

        # Simulate a counter reset on the second observation.
        dataset.loc[1, "rx_packets"] = 20

        processed = prepare_counter_deltas(dataset)
        reset_row = processed.iloc[1]

        self.assertEqual(reset_row["state"], "counter_reset")
        self.assertTrue(bool(reset_row["is_counter_reset"]))

        delta_columns = [
            f"{column}_delta" for column in COUNTER_COLUMNS
        ]

        self.assertTrue(
            reset_row[delta_columns].isna().all(),
            "All counter deltas must be missing after a reset.",
        )


    def test_long_sampling_gap_is_flagged(self):
        dataset = self.make_dataset()

        # Move the second observation 30 seconds after the first.
        dataset.loc[1, "timestamp"] = 1030.0

        processed = prepare_counter_deltas(dataset)
        second = processed.iloc[1]

        self.assertEqual(second["interval_seconds"], 30.0)
        self.assertEqual(second["state"], "long_gap")
        self.assertTrue(bool(second["is_long_gap"]))


    def test_each_port_has_its_own_initial_observation(self):
        dataset = self.make_dataset()

        second_port = dataset.iloc[[0]].copy()
        second_port["id"] = 3
        second_port["port"] = "2"
        second_port["timestamp"] = 1002.0
        second_port["rx_packets"] = 500
        second_port["rx_bytes"] = 5000

        dataset = pd.concat(
            [dataset, second_port],
            ignore_index=True,
        )

        processed = prepare_counter_deltas(dataset)

        port_two_first = processed[
            processed["port"].astype(str) == "2"
        ].iloc[0]

        self.assertEqual(port_two_first["state"], "initial")
        self.assertTrue(pd.isna(port_two_first["rx_packets_delta"]))


    def test_missing_required_column_raises_value_error(self):
        dataset = self.make_dataset()
        dataset = dataset.drop(columns=["timestamp"])

        with self.assertRaisesRegex(
            ValueError, "missing required columns"
        ):
            prepare_counter_deltas(dataset)


    def test_local_port_is_excluded(self):
        dataset = self.make_dataset()

        local_row = dataset.iloc[[0]].copy()
        local_row["id"] = 3
        local_row["port"] = "LOCAL"
        local_row["timestamp"] = 1001.0

        dataset = pd.concat(
            [dataset, local_row],
            ignore_index=True,
        )

        processed = prepare_counter_deltas(dataset)

        self.assertFalse(
            (processed["port"].astype(str) == "LOCAL").any()
        )
        self.assertEqual(len(processed), 2)


    def test_reset_during_long_gap_preserves_both_flags(self):
        dataset = self.make_dataset()

        dataset.loc[1, "timestamp"] = 1030.0
        dataset.loc[1, "rx_packets"] = 20

        processed = prepare_counter_deltas(dataset)
        row = processed.iloc[1]

        self.assertEqual(row["state"], "counter_reset")
        self.assertTrue(bool(row["is_counter_reset"]))
        self.assertTrue(bool(row["is_long_gap"]))

        delta_columns = [
            f"{column}_delta" for column in COUNTER_COLUMNS
        ]
        self.assertTrue(row[delta_columns].isna().all())


    def test_input_dataset_is_not_modified(self):
        dataset = self.make_dataset()
        original = dataset.copy(deep=True)

        prepare_counter_deltas(dataset)

        pd.testing.assert_frame_equal(dataset, original)


if __name__ == "__main__":
    unittest.main()
