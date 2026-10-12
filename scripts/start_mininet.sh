#!/usr/bin/env bash
# TERMINAL 2 - Mininet redundant topology (start after the controller shows it is listening)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
as_root mn -c >/dev/null 2>&1
as_root env PYTHONPATH="$PROJECT" mn --custom sdn_controller/topologies/redundant_topology.py \
  --topo redundant --controller remote,ip=127.0.0.1,port=6653 \
  --switch ovs,protocols=OpenFlow13
