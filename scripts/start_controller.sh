#!/usr/bin/env bash
# TERMINAL 1 - Ryu self-healing controller (start this first)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
echo "Starting Ryu controller with $RYU_PY (Ctrl+C to stop)"
exec "$RYU_PY" -m ryu.cmd.manager --observe-links sdn_controller/self_healing_controller.py
