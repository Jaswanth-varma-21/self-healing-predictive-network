import os
import shutil
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ovs_parser import parse_ovs_port_stats


def _ovs_ofctl_command(switch):
    """Build the dump-ports command; use sudo only when needed and available."""
    ofctl = shutil.which("ovs-ofctl") or "/usr/bin/ovs-ofctl"
    command = [ofctl, "-O", "OpenFlow13", "dump-ports", switch]
    if hasattr(os, "geteuid") and os.geteuid() != 0 and shutil.which("sudo"):
        command.insert(0, "sudo")
    return command


def get_ovs_port_stats(switch):
    try:
        result = subprocess.run(
            _ovs_ofctl_command(switch),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return {"return_code": 127, "stdout": "", "stderr": str(exc), "records": []}

    records = []
    if result.returncode == 0:
        records = parse_ovs_port_stats(result.stdout)

    return {
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "records": records,
    }


if __name__ == "__main__":
    result = get_ovs_port_stats("s1")
    print(result)
