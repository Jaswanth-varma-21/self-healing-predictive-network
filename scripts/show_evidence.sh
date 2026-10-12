#!/usr/bin/env bash
# TERMINAL 4 - print live evidence (flows, port counters, link state, audit trail)
# usage: bash scripts/show_evidence.sh [switch]   (default: s1)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
SW="${1:-s1}"
echo "=== $(date '+%F %T') flow table: $SW ==="
as_root ovs-ofctl -O OpenFlow13 dump-flows "$SW"
echo; echo "=== port counters: s3 (alternate path) ==="
as_root ovs-ofctl -O OpenFlow13 dump-ports s3
echo; echo "=== link state ==="
for br in s1 s2 s3; do
  for i in $(as_root ovs-vsctl list-ports "$br" 2>/dev/null); do
    printf '%s: ' "$i"; as_root ovs-vsctl get Interface "$i" link_state 2>/dev/null || echo unknown
  done
done
echo; echo "=== last audit events ==="
tail -n 8 logs/security_audit.jsonl 2>/dev/null || echo "(no audit events yet)"
