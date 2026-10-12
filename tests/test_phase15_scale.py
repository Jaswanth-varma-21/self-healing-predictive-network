import unittest

from experiments.large_scale import make_redundant_graph, shortest_path, run_scale_experiments


class TestPhase15Scale(unittest.TestCase):
    def test_single_ring_link_failure_preserves_reachability(self):
        graph = make_redundant_graph(8)
        path = shortest_path(graph, "n0", "n7", [("n0", "n1")])
        self.assertIsNotNone(path)
        self.assertNotIn("n1", path[1:2])

    def test_scale_results_are_explicitly_simulated(self):
        rows = run_scale_experiments(sizes=(5, 10), repetitions=2)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["live_mininet"] is False for row in rows))
        self.assertTrue(all(row["reachable_after_failure"] for row in rows))

    def test_invalid_topology_size_rejected(self):
        with self.assertRaises(ValueError):
            make_redundant_graph(2)


if __name__ == "__main__":
    unittest.main()
