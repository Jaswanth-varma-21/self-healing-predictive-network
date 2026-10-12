#!/usr/bin/env bash
# Optional: create a Ryu virtualenv at ~/ryu-env.  bash scripts/setup_ryu_env.sh
# Ryu 4.34 is old; it is most reliable on Python 3.8-3.9 (pin shown below).
# If you already have a working Ryu environment, skip this and set RYU_PY instead.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
TARGET="${1:-$HOME/ryu-env}"
python3 -m venv "$TARGET"
"$TARGET/bin/pip" install --upgrade pip wheel "setuptools<58"
"$TARGET/bin/pip" install "eventlet==0.30.2" "ryu==4.34"
"$TARGET/bin/python" -c "import ryu; print('Ryu', ryu.__version__, 'installed in', '$TARGET')"
echo "Use it with: export RYU_PY=$TARGET/bin/python"
