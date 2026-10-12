#!/usr/bin/env bash
# TERMINAL 3 - Sentinel Twin dashboard -> http://127.0.0.1:8765
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
exec python3 demo/live_demo.py "$@"
