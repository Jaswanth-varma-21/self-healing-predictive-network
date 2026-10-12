#!/usr/bin/env bash
# Pre-demo check:  bash scripts/check_env.sh   (read-only; changes nothing)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
fail=0
ok()   { printf '  [ OK ] %s\n' "$1"; }
bad()  { printf '  [FAIL] %s\n' "$1"; fail=1; }
warn() { printf '  [WARN] %s\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

echo "Project: $PROJECT"
echo "Ryu python: $RYU_PY"
echo "== Tools =="
for t in python3 mn ovs-vsctl ovs-ofctl ip ping curl; do
  have "$t" && ok "$t found" || bad "$t missing (bash scripts/setup_debian.sh)"
done
[ "$(id -u)" -eq 0 ] || have sudo && ok "root or sudo available" || bad "need root or sudo"

echo "== Python packages (dashboard / learning card) =="
python3 -c "import numpy, pandas, sklearn" 2>/dev/null && ok "numpy, pandas, scikit-learn" || bad "install: pip install -r requirements.txt"

echo "== Ryu =="
"$RYU_PY" -c "import ryu; print('ryu import OK')" 2>/dev/null && ok "Ryu importable" || bad "Ryu missing for $RYU_PY (bash scripts/setup_ryu_env.sh or export RYU_PY=...)"
"$RYU_PY" -c "import sys; sys.path.insert(0,'$PROJECT'); import security.trust_layer" 2>/dev/null && ok "project imports under Ryu python" || bad "project import failed under Ryu python"

echo "== Open vSwitch =="
if have ovs-vsctl; then
  as_root ovs-vsctl show >/dev/null 2>&1 && ok "ovs-vswitchd responding" || bad "Open vSwitch not running: sudo systemctl start openvswitch-switch"
fi

echo "== Ports =="
for port in 6653 8765; do
  if have ss && ss -ltn 2>/dev/null | grep -q ":$port "; then warn "port $port already in use"; else ok "port $port free"; fi
done

echo "== Project files and tests =="
[ -f telemetry/data/telemetry.db ] && ok "telemetry database present" || bad "telemetry/data/telemetry.db missing"
if python3 -m unittest discover -s tests >/tmp/cn_tests.log 2>&1; then ok "unit tests: $(grep -E '^Ran' /tmp/cn_tests.log)"; else bad "unit tests failed (see /tmp/cn_tests.log)"; fi

echo
[ "$fail" -eq 0 ] && echo "READY for the demo." || { echo "Fix the [FAIL] items above first."; exit 1; }
