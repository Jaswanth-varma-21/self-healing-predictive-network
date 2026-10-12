import subprocess
from pathlib import Path
import sys


def run_ping(target, count=20):
    result = subprocess.run(
        ["ping", "-c", str(count), target],
        capture_output=True,
        text=True,
        check=False,
    )

    return {
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def parse_ping_output(output):
    import re

    packet_match = re.search(
        r"(\d+) packets transmitted, (\d+) received, (?:\+\d+ corrupted, )?([\d.]+)% packet loss",
        output,
    )

    rtt_match = re.search(
        r"rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms",
        output,
    )

    if not packet_match:
        raise ValueError("Could not parse packet statistics")

    if not rtt_match:
        raise ValueError("Could not parse RTT statistics")

    return {
        "packets_transmitted": int(packet_match.group(1)),
        "packets_received": int(packet_match.group(2)),
        "packet_loss_percent": float(packet_match.group(3)),
        "rtt_min_ms": float(rtt_match.group(1)),
        "rtt_avg_ms": float(rtt_match.group(2)),
        "rtt_max_ms": float(rtt_match.group(3)),
        "rtt_mdev_ms": float(rtt_match.group(4)),
    }


def collect_ping_telemetry(target, count=20):
    result = run_ping(target, count)

    if result["return_code"] != 0:
        return {
            "success": False,
            "error": result["stderr"].strip() or "Ping failed",
            "metrics": {},
        }

    metrics = parse_ping_output(result["stdout"])

    return {
        "success": True,
        "error": None,
        "metrics": metrics,
    }


def store_ping_telemetry(node, target, metrics):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

    from telemetry_pipeline import store_telemetry

    store_telemetry(
        "ping",
        node,
        target,
        metrics,
    )
