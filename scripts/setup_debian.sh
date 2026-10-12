#!/usr/bin/env bash
# One-time Debian setup (run once, needs root or sudo):  bash scripts/setup_debian.sh
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

echo "== Installing system packages =="
as_root apt-get update
as_root apt-get install -y mininet openvswitch-switch iproute2 iputils-ping curl \
  python3 python3-venv python3-pip python3-numpy python3-pandas python3-sklearn

echo "== Starting Open vSwitch =="
as_root systemctl enable --now openvswitch-switch 2>/dev/null || as_root service openvswitch-switch start || true

echo "== Done. Ryu is installed separately (see scripts/setup_ryu_env.sh) =="
echo "Next: bash scripts/check_env.sh"
