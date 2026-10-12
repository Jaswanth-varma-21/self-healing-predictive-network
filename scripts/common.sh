#!/usr/bin/env bash
# Shared settings for the demo scripts. Source this file; do not run it.
PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PROJECT
cd "$PROJECT" || exit 1

# Python that has Ryu installed. Override with: export RYU_PY=/path/to/python
if [ -z "${RYU_PY:-}" ]; then
  for candidate in "$HOME/ryu-env/bin/python" "$PROJECT/.ryu-env/bin/python" "$(command -v python3)"; do
    if [ -x "$candidate" ] && "$candidate" -c "import ryu" >/dev/null 2>&1; then
      RYU_PY="$candidate"; break
    fi
  done
fi
export RYU_PY="${RYU_PY:-$(command -v python3)}"

# Run a command as root only when necessary (minimal Debian may not have sudo).
as_root() {
  if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi
}
