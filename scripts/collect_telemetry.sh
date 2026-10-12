#!/usr/bin/env bash
# TERMINAL 4 - collect fresh Open vSwitch port counters into the telemetry DB
# (ovs-ofctl is called through sudo automatically when you are not root)
# usage: bash scripts/collect_telemetry.sh [switch] [samples]   (default: s1 5)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
SWITCH="${1:-s1}"; SAMPLES="${2:-5}"
python3 -c "
import sys; sys.path.insert(0, '$PROJECT')
from telemetry.pipeline.telemetry_pipeline import run_ovs_collection_loop
run_ovs_collection_loop('$SWITCH', $SAMPLES)"
