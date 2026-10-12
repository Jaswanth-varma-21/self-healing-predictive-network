import unittest
from unittest.mock import patch

from demo import live_demo
from telemetry import ovs_telemetry


def _ports(table):
    return {name: (idx, peer) for name, idx, peer in table}


class TestPortDiscovery(unittest.TestCase):
    def edge_ports(self, interfaces):
        edges = live_demo.discover_edges(interfaces)
        self.assertIsNotNone(edges)
        return {e["id"]: e["ports"] for e in edges}

    def test_link_creation_order_s2_host_first(self):
        # s2-eth1 -> h2, s2-eth2 -> s1, s2-eth3 -> s3
        result = self.edge_ports(_ports([
            ("s1-eth1", 11, 900), ("s1-eth2", 12, 22), ("s1-eth3", 13, 31),
            ("s2-eth1", 21, 901), ("s2-eth2", 22, 12), ("s2-eth3", 23, 32),
            ("s3-eth1", 31, 13), ("s3-eth2", 32, 23),
        ]))
        self.assertEqual(result["s1-s2"], ["s1-eth2", "s2-eth2"])
        self.assertEqual(result["s3-s2"], ["s2-eth3", "s3-eth2"])
        self.assertEqual(result["s2-h2"], ["s2-eth1"])
        self.assertEqual(result["h1-s1"], ["s1-eth1"])

    def test_sorted_link_order_s2_host_second(self):
        # s2-eth1 -> s1, s2-eth2 -> h2, s2-eth3 -> s3
        result = self.edge_ports(_ports([
            ("s1-eth1", 11, 900), ("s1-eth2", 12, 21), ("s1-eth3", 13, 31),
            ("s2-eth1", 21, 12), ("s2-eth2", 22, 901), ("s2-eth3", 23, 32),
            ("s3-eth1", 31, 13), ("s3-eth2", 32, 23),
        ]))
        self.assertEqual(result["s1-s2"], ["s1-eth2", "s2-eth1"])
        self.assertEqual(result["s3-s2"], ["s2-eth3", "s3-eth2"])
        self.assertEqual(result["s2-h2"], ["s2-eth2"])

    def test_unrecognised_topology_falls_back(self):
        self.assertIsNone(live_demo.discover_edges({}))
        with patch.object(live_demo, "read_switch_interfaces", return_value={}):
            self.assertEqual(live_demo.current_edges(), live_demo.EDGES)

    def test_edge_order_matches_frontend(self):
        edges = live_demo.discover_edges(_ports([
            ("s1-eth1", 11, 900), ("s1-eth2", 12, 22), ("s1-eth3", 13, 31),
            ("s2-eth1", 21, 901), ("s2-eth2", 22, 12), ("s2-eth3", 23, 32),
            ("s3-eth1", 31, 13), ("s3-eth2", 32, 23),
        ]))
        self.assertEqual([e["id"] for e in edges], [e["id"] for e in live_demo.EDGES])


class TestOvsCommand(unittest.TestCase):
    def test_no_sudo_for_root(self):
        with patch.object(ovs_telemetry.os, "geteuid", return_value=0):
            self.assertNotIn("sudo", ovs_telemetry._ovs_ofctl_command("s1"))

    def test_missing_binary_is_reported_not_raised(self):
        with patch.object(ovs_telemetry.subprocess, "run", side_effect=FileNotFoundError("ovs-ofctl")):
            result = ovs_telemetry.get_ovs_port_stats("s1")
        self.assertEqual(result["return_code"], 127)
        self.assertEqual(result["records"], [])


if __name__ == "__main__":
    unittest.main()
