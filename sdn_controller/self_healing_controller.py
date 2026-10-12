from collections import defaultdict, deque

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (
    CONFIG_DISPATCHER,
    MAIN_DISPATCHER,
    DEAD_DISPATCHER,
    set_ev_cls,
)
from ryu.ofproto import ofproto_v1_3
from ryu.topology import event
from ryu.topology.api import get_link, get_switch
from ryu.lib.packet import packet, ethernet, ether_types

from security.trust_layer import audit_event, validate_path


class SelfHealingController(app_manager.RyuApp):
    """Learning SDN switch with topology-aware path recomputation."""

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.datapaths = {}
        self.host_locations = {}
        self.adjacency = defaultdict(dict)
        self.port_to_neighbor = {}
        self.failed_ports = set()

    def add_flow(self, datapath, priority, match, actions):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS, actions
            )
        ]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            cookie=0x20 if priority == 20 else 0,
            priority=priority,
            match=match,
            instructions=instructions,
        )
        datapath.send_msg(mod)

    def delete_all_flows(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        match = parser.OFPMatch()
        mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            match=match,
        )
        datapath.send_msg(mod)

    def delete_forwarding_flows(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        mod = parser.OFPFlowMod(
            datapath=datapath,
            cookie=0x20,
            cookie_mask=0xFFFFFFFFFFFFFFFF,
            command=ofproto.OFPFC_DELETE,
            table_id=ofproto.OFPTT_ALL,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            match=parser.OFPMatch(),
        )
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.datapaths[datapath.id] = datapath
        self.add_flow(
            datapath,
            0,
            datapath.ofproto_parser.OFPMatch(),
            [datapath.ofproto_parser.OFPActionOutput(
                datapath.ofproto.OFPP_CONTROLLER,
                datapath.ofproto.OFPCML_NO_BUFFER,
            )],
        )
        self.logger.info("Switch connected: dpid=%s", datapath.id)

    @set_ev_cls(
        ofp_event.EventOFPStateChange,
        [MAIN_DISPATCHER, DEAD_DISPATCHER],
    )
    def state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)
            self.logger.warning("Switch disconnected: dpid=%s", datapath.id)

    def rebuild_topology(self):
        self.adjacency.clear()
        self.port_to_neighbor.clear()

        switches = get_switch(self, None)
        for switch in switches:
            self.adjacency.setdefault(switch.dp.id, {})

        for link in get_link(self, None):
            src = link.src.dpid
            dst = link.dst.dpid
            src_port = link.src.port_no
            dst_port = link.dst.port_no

            if (src, src_port) in self.failed_ports:
                continue
            if (dst, dst_port) in self.failed_ports:
                continue

            self.adjacency[src][dst] = src_port
            self.port_to_neighbor[(src, src_port)] = (dst, dst_port)

        self.logger.info(
            "Topology refreshed: switches=%d directed_links=%d",
            len(self.adjacency),
            sum(len(neighbors) for neighbors in self.adjacency.values()),
        )

    def shortest_path(self, source, destination):
        if source == destination:
            return [source]

        queue = deque([(source, [source])])
        visited = {source}

        while queue:
            node, path = queue.popleft()
            for neighbor in sorted(self.adjacency.get(node, {})):
                if neighbor in visited:
                    continue
                new_path = path + [neighbor]
                if neighbor == destination:
                    return new_path
                visited.add(neighbor)
                queue.append((neighbor, new_path))

        return None

    def failed_link_pairs(self):
        """Return known failed inter-switch links as undirected DPID pairs."""
        pairs = set()
        for (dpid, port), (neighbor, _neighbor_port) in self.port_to_neighbor.items():
            if (dpid, port) in self.failed_ports:
                pairs.add((dpid, neighbor))
        return pairs

    def install_host_path(self, src_mac, dst_mac):
        src_location = self.host_locations.get(src_mac)
        dst_location = self.host_locations.get(dst_mac)
        if not src_location or not dst_location:
            return

        src_dpid, src_host_port = src_location
        dst_dpid, dst_host_port = dst_location
        path = self.shortest_path(src_dpid, dst_dpid)

        if not path:
            audit_event(
                "forwarding_path_validation", "rejected",
                source=src_mac, destination=dst_mac, reason="no path available",
            )
            self.logger.warning(
                "No path available between hosts %s and %s",
                src_mac, dst_mac,
            )
            return

        path_ok, path_reason = validate_path(path, self.adjacency, self.failed_link_pairs())
        audit_event(
            "forwarding_path_validation",
            "approved" if path_ok else "rejected",
            source=src_mac, destination=dst_mac, path=path, reason=path_reason,
        )
        if not path_ok:
            self.logger.warning("Rejected unsafe forwarding path %s: %s", path, path_reason)
            return

        # Preflight every switch and port before installing any flow. This avoids
        # partially programming a route if a datapath/port is missing mid-path.
        plan = []
        for index, dpid in enumerate(path):
            datapath = self.datapaths.get(dpid)
            if datapath is None:
                audit_event(
                    "forwarding_path_install", "rejected",
                    source=src_mac, destination=dst_mac, path=path,
                    reason=f"switch {dpid} is not connected",
                )
                return

            if index == len(path) - 1:
                out_port = dst_host_port
            else:
                next_dpid = path[index + 1]
                out_port = self.adjacency[dpid].get(next_dpid)
            in_port = (
                src_host_port if index == 0
                else self.adjacency[dpid].get(path[index - 1])
            )
            if out_port is None or in_port is None:
                audit_event(
                    "forwarding_path_install", "rejected",
                    source=src_mac, destination=dst_mac, path=path,
                    reason=f"missing input/output port on switch {dpid}",
                )
                return
            plan.append((datapath, in_port, out_port))

        for datapath, in_port, out_port in plan:
            parser = datapath.ofproto_parser
            match = parser.OFPMatch(
                in_port=in_port,
                eth_src=src_mac,
                eth_dst=dst_mac,
            )
            actions = [parser.OFPActionOutput(out_port)]
            self.add_flow(datapath, 20, match, actions)

        self.logger.info(
            "Forwarding path installed: %s -> %s via %s",
            src_mac, dst_mac, path,
        )

    def recompute_known_paths(self):
        for datapath in list(self.datapaths.values()):
            self.delete_forwarding_flows(datapath)
        hosts = list(self.host_locations)
        for src_mac in hosts:
            for dst_mac in hosts:
                if src_mac != dst_mac:
                    self.install_host_path(src_mac, dst_mac)

    @set_ev_cls(event.EventSwitchEnter)
    @set_ev_cls(event.EventLinkAdd)
    @set_ev_cls(event.EventLinkDelete)
    def topology_change_handler(self, ev):
        self.rebuild_topology()
        self.recompute_known_paths()

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_status_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        reason = msg.reason
        port_no = msg.desc.port_no
        ofproto = datapath.ofproto

        if reason == ofproto.OFPPR_DELETE:
            self.failed_ports.add((datapath.id, port_no))
            self.logger.warning(
                "Port deleted: switch=%s port=%s",
                datapath.id, port_no,
            )
        elif reason == ofproto.OFPPR_MODIFY:
            state = msg.desc.state
            if state & ofproto.OFPPS_LINK_DOWN:
                self.failed_ports.add((datapath.id, port_no))
                self.logger.warning(
                    "Port link down: switch=%s port=%s",
                    datapath.id, port_no,
                )
            else:
                self.failed_ports.discard((datapath.id, port_no))
                self.logger.info(
                    "Port link restored: switch=%s port=%s",
                    datapath.id, port_no,
                )

        self.rebuild_topology()
        self.recompute_known_paths()

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None or eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        src_mac = eth.src
        dst_mac = eth.dst
        dpid = datapath.id
        self.logger.info("PACKET_IN: switch=%s port=%s src=%s dst=%s", dpid, in_port, src_mac, dst_mac)

        # Learn only host-facing ports, not ports known to connect switches.
        if (dpid, in_port) not in self.port_to_neighbor:
            self.host_locations[src_mac] = (dpid, in_port)

        if dst_mac in self.host_locations:
            self.install_host_path(src_mac, dst_mac)
            path = self.shortest_path(
                dpid, self.host_locations[dst_mac][0]
            )
            if path and len(path) > 1:
                next_dpid = path[1]
                out_port = self.adjacency[dpid].get(next_dpid)
            else:
                out_port = self.host_locations[dst_mac][1]
        else:
            out_port = datapath.ofproto.OFPP_FLOOD

        actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=None if msg.buffer_id != datapath.ofproto.OFP_NO_BUFFER
            else msg.data,
        )
        datapath.send_msg(out)


if __name__ == "__main__":
    print("SELF_HEALING_CONTROLLER_MODULE: PASS")
