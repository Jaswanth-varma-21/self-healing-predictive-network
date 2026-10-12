#!/usr/bin/python3

from mininet.topo import Topo


class RedundantTopology(Topo):
    """Two hosts connected through a primary and an alternate switch path."""

    def build(self):
        h1 = self.addHost("h1", ip="10.0.0.1/24")
        h2 = self.addHost("h2", ip="10.0.0.2/24")

        s1 = self.addSwitch("s1", protocols="OpenFlow13")
        s2 = self.addSwitch("s2", protocols="OpenFlow13")
        s3 = self.addSwitch("s3", protocols="OpenFlow13")

        # Host access links
        self.addLink(h1, s1)
        self.addLink(s2, h2)

        # Primary path
        self.addLink(s1, s2)

        # Alternate path
        self.addLink(s1, s3)
        self.addLink(s3, s2)


topos = {"redundant": lambda: RedundantTopology()}


if __name__ == "__main__":
    topology = RedundantTopology()
    print("TOPOLOGY_NAME: redundant")
    print("HOSTS:", sorted(topology.hosts()))
    print("SWITCHES:", sorted(topology.switches()))
    print("LINK_COUNT:", len(topology.links()))
    assert len(topology.hosts()) == 2
    assert len(topology.switches()) == 3
    assert len(topology.links()) == 5
    print("REDUNDANT_TOPOLOGY_DEFINITION: PASS")
