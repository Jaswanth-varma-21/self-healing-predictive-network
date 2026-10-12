#!/usr/bin/env python3
"""Sentinel Twin v2 live dashboard for the digital twin + self-healing network project.

The dashboard polls actual SQLite/OVS status. Scenario buttons operate only on
an in-memory twin simulation and never execute shell commands or change Mininet.
Bind to loopback by default.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import math
import os
import re
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

_HERE = Path(__file__).resolve().parent
# Normally this script sits in a sub-folder (e.g. demo/). If it was dropped
# straight into the project root, use its own folder instead.
if (_HERE / "telemetry").exists() and not (_HERE.parent / "telemetry").exists():
    PROJECT_ROOT = _HERE
else:
    PROJECT_ROOT = _HERE.parent


def resolve_database_path() -> Path:
    """Prefer the configured DB when valid, otherwise discover the project DB.

    This handles ZIPs extracted into an extra folder and stale CN_TELEMETRY_DB
    environment variables without silently creating a new empty database.
    """
    configured = os.environ.get("CN_TELEMETRY_DB")
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend([
        PROJECT_ROOT / "telemetry" / "data" / "telemetry.db",
        Path.cwd() / "telemetry" / "data" / "telemetry.db",
        PROJECT_ROOT.parent / "telemetry" / "data" / "telemetry.db",
        PROJECT_ROOT.parent / "cn_project" / "telemetry" / "data" / "telemetry.db",
    ])
    seen = set()
    for candidate in candidates:
        try:
            candidate = candidate.resolve()
        except OSError:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file():
            return candidate
    # Keep the canonical location for useful missing-file diagnostics.
    return (Path(configured).expanduser() if configured else
            PROJECT_ROOT / "telemetry" / "data" / "telemetry.db")


DB_PATH = resolve_database_path()
PORT = 8765

EDGES = [
    {"id": "h1-s1", "a": "h1", "b": "s1", "ports": ["s1-eth1"]},
    {"id": "s1-s2", "a": "s1", "b": "s2", "ports": ["s1-eth2", "s2-eth1"]},
    {"id": "s1-s3", "a": "s1", "b": "s3", "ports": ["s1-eth3", "s3-eth1"]},
    {"id": "s3-s2", "a": "s3", "b": "s2", "ports": ["s3-eth2", "s2-eth2"]},
    {"id": "s2-h2", "a": "s2", "b": "h2", "ports": ["s2-eth3"]},
]
SIMULATION_SCENARIOS = {
    "normal": {
        "title": "Normal network",
        "risk": "LOW",
        "twin": "SYNCHRONIZED",
        "cause": "No abnormal condition observed in this simulation",
        "action": "NO ACTION",
        "verification": "Healthy state maintained",
        "packet_loss_percent": 0.0,
        "latency_ms": 2.4,
        "events": ["Twin synchronized", "No anomaly", "Recovery suppressed by policy"],
    },
    "congestion": {
        "title": "Congestion detected",
        "risk": "HIGH",
        "twin": "DIVERGENCE DETECTED",
        "cause": "Queue pressure / rising delay (simulated causal hypothesis)",
        "action": "EVALUATE ALTERNATE ROUTE",
        "verification": "Candidate action evaluated in twin only",
        "packet_loss_percent": 18.0,
        "latency_ms": 72.0,
        "events": ["Telemetry deviation injected into simulation", "Causal hypothesis ranked", "Counterfactual route evaluated"],
    },
    "link_failure": {
        "title": "Primary link failure",
        "risk": "CRITICAL",
        "twin": "LINK STATE CHANGED",
        "cause": "Primary inter-switch link unavailable (simulated)",
        "action": "REROUTE VIA s3",
        "verification": "Simulated alternate path remains reachable",
        "packet_loss_percent": 0.0,
        "latency_ms": 4.8,
        "events": ["Simulated s1-s2 failure", "Primary route rejected", "Alternate path via s3 selected", "Twin reachability check passed"],
    },
    "recovery_failure": {
        "title": "Recovery failure / rollback",
        "risk": "CRITICAL",
        "twin": "FIRST ACTION FAILED",
        "cause": "First candidate route did not improve simulated reachability",
        "action": "SECOND STRATEGY + ROLLBACK",
        "verification": "Known-good alternate path restored in simulation",
        "packet_loss_percent": 0.0,
        "latency_ms": 5.1,
        "events": ["First recovery strategy failed", "Post-action verification detected failure", "Unsafe candidate rolled back", "Second strategy verified in twin"],
    },
}
_STATE_LOCK = threading.Lock()
_SIM_STATE = {"scenario": "normal", "started_at": time.time(), "event_id": 1}


def run_command(args: list[str], timeout: float = 1.5) -> str | None:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None
    return None


def ttl_cached(seconds: float):
    """Cache a no-argument probe so 2 s polling never stacks up slow commands."""
    def decorator(fn):
        lock = threading.Lock()
        box = {"at": 0.0, "value": None}

        def wrapper():
            with lock:
                if box["value"] is None or time.monotonic() - box["at"] >= seconds:
                    box["value"] = fn()
                    box["at"] = time.monotonic()
                return box["value"]
        return wrapper
    return decorator


def interface_status(name: str) -> str:
    """Return up/down/unknown without confusing the interface name with flags.

    `ip -o link` looks like `2: s1-eth1: <BROADCAST,MULTICAST,UP,LOWER_UP> ...`.
    Parsing the second colon-delimited field reads the *name*, not the flags;
    that was causing live interfaces to be incorrectly reported as down.
    """
    value = run_command(["ovs-vsctl", "get", "Interface", name, "link_state"])
    if value:
        value = value.strip().strip('"').lower()
        if value in ("up", "down"):
            return value

    value = run_command(["ip", "-o", "link", "show", "dev", name])
    if not value:
        return "unknown"
    match = re.search(r"<([^>]*)>", value)
    if not match:
        return "unknown"
    flags = {part.strip().upper() for part in match.group(1).split(",")}
    if "UP" not in flags:
        return "down"
    if "NO-CARRIER" in flags:
        return "down"
    if "LOWER_UP" in flags:
        return "up"
    # Interface exists and is administratively up, but has no active carrier.
    return "down"


_SWITCH_PORT = re.compile(r"^(s\d+)-eth\d+$")
_PAIR_TO_EDGE = {
    frozenset({"s1", "s2"}): "s1-s2",
    frozenset({"s1", "s3"}): "s1-s3",
    frozenset({"s2", "s3"}): "s3-s2",
}


def read_switch_interfaces(sysfs: str = "/sys/class/net") -> dict:
    """Return {interface: (ifindex, peer_ifindex)} for Mininet switch ports."""
    found = {}
    try:
        names = os.listdir(sysfs)
    except OSError:
        return found
    for name in names:
        if not _SWITCH_PORT.match(name):
            continue
        try:
            index = int(Path(sysfs, name, "ifindex").read_text())
            peer = int(Path(sysfs, name, "iflink").read_text())
        except (OSError, ValueError):
            continue
        found[name] = (index, peer)
    return found


def discover_edges(interfaces: dict) -> list[dict] | None:
    """Work out which switch ports belong to which link from veth peer indexes.

    Mininet numbers ports by link-creation order, so port numbers are not safe to
    hard-code. A port whose peer is another switch port is an inter-switch link;
    a port whose peer is not visible is host-facing. Returns None if the live
    topology cannot be recognised (caller falls back to the static EDGES).
    """
    by_index = {idx: name for name, (idx, _peer) in interfaces.items()}
    switch_pairs: dict[frozenset, list[str]] = {}
    host_ports: dict[str, list[str]] = {}
    for name, (_idx, peer) in sorted(interfaces.items()):
        switch = _SWITCH_PORT.match(name).group(1)
        peer_name = by_index.get(peer)
        if peer_name is None:
            host_ports.setdefault(switch, []).append(name)
            continue
        pair = frozenset({switch, _SWITCH_PORT.match(peer_name).group(1)})
        ports = switch_pairs.setdefault(pair, [])
        if name not in ports:
            ports.append(name)
    if set(switch_pairs) != set(_PAIR_TO_EDGE) or len(host_ports.get("s1", [])) != 1 or len(host_ports.get("s2", [])) != 1:
        return None
    edges = [{"id": "h1-s1", "a": "h1", "b": "s1", "ports": host_ports["s1"]}]
    for pair, edge_id in _PAIR_TO_EDGE.items():
        a, b = edge_id.split("-")
        edges.append({"id": edge_id, "a": a, "b": b, "ports": sorted(switch_pairs[pair])})
    edges.append({"id": "s2-h2", "a": "s2", "b": "h2", "ports": host_ports["s2"]})
    order = {edge["id"]: i for i, edge in enumerate(EDGES)}
    return sorted(edges, key=lambda e: order[e["id"]])


def current_edges() -> list[dict]:
    return discover_edges(read_switch_interfaces()) or EDGES


# ---------------------------------------------------------------------------
# Emulated network runtime. When no Mininet/OVS interfaces exist on this machine
# (or the user deploys a custom design) the dashboard "runs" the topology
# in-process: links are up until failed/restored, and every change is recorded
# as a demo feedback sample so the learning-readiness KPI moves. It never
# executes shell commands and never touches a real network.
# ---------------------------------------------------------------------------
_NET_LOCK = threading.Lock()
_NET = {"design": None, "failed": set()}
_FEEDBACK: list[dict] = []
_NODE_ID = re.compile(r"^[hs]\d{1,2}$")
MIN_PER_CLASS = 5


def default_design() -> dict:
    return {"nodes": ["h1", "s1", "s2", "s3", "h2"], "edges": [(e["a"], e["b"]) for e in EDGES]}


def record_feedback(label: str, kind: str) -> None:
    with _NET_LOCK:
        _FEEDBACK.append({"t": time.time(), "label": label, "kind": kind})
        del _FEEDBACK[:-500]


def network_mode() -> str:
    with _NET_LOCK:
        deployed = _NET["design"] is not None
    if deployed or not read_switch_interfaces():
        return "emulated"
    return "mininet"


def emulated_links() -> list[dict]:
    with _NET_LOCK:
        design = _NET["design"] or default_design()
        failed = set(_NET["failed"])
    out = []
    for a, b in design["edges"]:
        eid = f"{a}-{b}"
        out.append({"id": eid, "a": a, "b": b, "ports": [], "port_states": [],
                    "status": "down" if eid in failed else "up", "emulated": True})
    return out


def deploy_design(payload) -> None:
    if not isinstance(payload, dict):
        raise ValueError("design must be an object")
    nodes, edges = payload.get("nodes"), payload.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("design needs nodes and edges lists")
    if not 2 <= len(nodes) <= 24 or len(edges) > 80:
        raise ValueError("design must have 2-24 devices and at most 80 links")
    if len(set(nodes)) != len(nodes) or not all(isinstance(n, str) and _NODE_ID.match(n) for n in nodes):
        raise ValueError("device names must look like h1 or s2 and be unique")
    if not edges:
        raise ValueError("add at least one connection before running the network")
    clean, seen = [], set()
    for item in edges:
        if not (isinstance(item, list) and len(item) == 2 and all(x in nodes for x in item)) or item[0] == item[1]:
            raise ValueError("every link must connect two different listed devices")
        key = frozenset(item)
        if key in seen:
            raise ValueError("duplicate link in design")
        seen.add(key)
        clean.append((item[0], item[1]))
    with _NET_LOCK:
        _NET["design"] = {"nodes": nodes, "edges": clean}
        _NET["failed"] = set()


def set_link(eid, down) -> None:
    if network_mode() != "emulated":
        raise ValueError("links can only be toggled in the emulated network")
    with _NET_LOCK:
        ids = {f"{a}-{b}" for a, b in (_NET["design"] or default_design())["edges"]}
        if eid not in ids:
            raise ValueError("unknown link")
        if down:
            _NET["failed"].add(eid)
        else:
            _NET["failed"].discard(eid)
    record_feedback("fault" if down else "healthy", "link_down" if down else "link_restored")


def live_links() -> list[dict]:
    if network_mode() == "emulated":
        return emulated_links()
    return _real_links()


@ttl_cached(1.5)
def _real_links() -> list[dict]:
    """Report link state and preserve per-interface evidence for diagnosis."""
    results = []
    for edge in current_edges():
        ports = edge.get("ports") or []
        port_states = [{"port": port, "status": interface_status(port)} for port in ports]
        states = [item["status"] for item in port_states]
        if not states:
            status = "unknown"
        elif "down" in states:
            status = "down"
        elif all(state == "up" for state in states):
            status = "up"
        else:
            status = "unknown"
        results.append({**edge, "status": status, "port_states": port_states})
    return results


def _clean(value, depth: int = 0):
    """Make decoded JSON safe for strict encoding (no NaN / Infinity)."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if depth > 6:
        return None
    if isinstance(value, dict):
        return {str(k): _clean(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v, depth + 1) for v in value[:50]]
    return value


def _normalize_metrics(raw: str) -> dict:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    if isinstance(value, dict) and isinstance(value.get("metrics"), dict):
        return _clean(value["metrics"])
    return _clean(value) if isinstance(value, dict) else {}


@ttl_cached(1.0)
def live_telemetry(limit: int = 30) -> dict:
    if not DB_PATH.exists():
        return {"database": "missing", "count": 0, "latest": [], "error": f"Database not found: {DB_PATH}"}
    try:
        with closing(sqlite3.connect(f"{DB_PATH.resolve().as_uri()}?mode=ro", uri=True, timeout=1.0)) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "telemetry" not in tables:
                return {"database": "connected", "count": 0, "latest": [], "error": "telemetry table not found"}
            count = conn.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]
            rows = conn.execute(
                "SELECT id, timestamp, source, node, port, metrics_json FROM telemetry ORDER BY timestamp DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        latest = [{
            "id": row[0], "timestamp": row[1], "source": row[2],
            "node": row[3], "port": row[4], "metrics": _normalize_metrics(row[5]),
        } for row in rows]
        return {"database": "connected", "count": count, "latest": latest, "error": None}
    except (sqlite3.Error, ValueError) as exc:
        return {"database": "error", "count": 0, "latest": [], "error": str(exc)}


def learning_status() -> dict:
    base = _project_learning()
    if base.get("ready_for_training") or (base.get("eligible_samples") or 0) > 0:
        return base
    with _NET_LOCK:
        counts = {"healthy": 0, "fault": 0}
        for item in _FEEDBACK:
            counts[item["label"]] += 1
    return {
        "ready_for_training": all(v >= MIN_PER_CLASS for v in counts.values()),
        "status": "demo", "source": "demo-session",
        "eligible_samples": sum(counts.values()),
        "minimum_per_class": MIN_PER_CLASS, "demo_counts": counts, "error": None,
    }


@ttl_cached(10.0)
def _project_learning() -> dict:
    try:
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        from failure_prediction.learning_trainer import load_eligible_feedback, check_training_readiness
        readiness = check_training_readiness(load_eligible_feedback())
        return readiness
    except Exception as exc:
        return {"ready_for_training": False, "status": "unavailable", "error": str(exc)}


def get_status() -> dict:
    telemetry = live_telemetry()
    with _STATE_LOCK:
        scenario_key = _SIM_STATE["scenario"]
        sim = dict(SIMULATION_SCENARIOS[scenario_key])
        sim.update({"scenario": scenario_key, "event_id": _SIM_STATE["event_id"], "started_at": _SIM_STATE["started_at"], "mode": "TWIN SIMULATION — NOT A LIVE NETWORK ACTION"})
    links = live_links()
    return {
        "project": "Self-Healing Predictive Network Using Digital Twin and Causal AI",
        "server_time": time.time(),
        "network": {"mode": network_mode()},
        "live": {"links": links, "up_links": sum(x["status"] == "up" for x in links), "down_links": sum(x["status"] == "down" for x in links), "unknown_links": sum(x["status"] == "unknown" for x in links), "telemetry": telemetry},
        "simulation": sim,
        "learning": learning_status(),
    }


def set_scenario(name: str) -> dict:
    if name not in SIMULATION_SCENARIOS:
        raise ValueError(f"scenario must be one of: {', '.join(SIMULATION_SCENARIOS)}")
    with _STATE_LOCK:
        _SIM_STATE.update({"scenario": name, "started_at": time.time(), "event_id": _SIM_STATE["event_id"] + 1})
    with _NET_LOCK:
        design = _NET["design"] or default_design()
        if "s1-s2" in {f"{a}-{b}" for a, b in design["edges"]}:
            _NET["failed"] = {"s1-s2"} if name in ("link_failure", "recovery_failure") else set()
    record_feedback("healthy" if name == "normal" else "fault", name)
    try:
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        from security.trust_layer import audit_event
        audit_event("demo_scenario", "simulation_only", scenario=name)
    except Exception:
        pass
    return get_status()


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sentinel Twin | Autonomous Network Lab</title>
<style>
:root{--bg:#07111f;--panel:#101f33;--panel2:#142740;--line:#29415d;--text:#edf5ff;--muted:#8fa8c4;--mint:#47e6ad;--blue:#63b8ff;--amber:#ffca70;--red:#ff687d}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 15% 0%,#15365a 0%,var(--bg) 42%);color:var(--text);font:14px/1.5 Inter,ui-sans-serif,system-ui,Segoe UI,Arial}
header{padding:24px clamp(18px,4vw,54px);border-bottom:1px solid #263c55;background:#091625d9;display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:13px}.logo{width:48px;height:48px;border-radius:15px;background:linear-gradient(135deg,#44e4b0,#318aff);display:grid;place-items:center;color:#061522;font-size:24px;font-weight:900;box-shadow:0 0 32px #39bcae35}
h1{margin:0;font-size:clamp(20px,3vw,29px);letter-spacing:-.7px}.subtitle{color:var(--muted);margin-top:4px}.pill{border:1px solid #2e506c;border-radius:999px;padding:7px 12px;color:var(--mint);background:#0c2531;font-weight:750;letter-spacing:.7px;font-size:11px}
main{max-width:1450px;margin:auto;padding:22px clamp(14px,3vw,38px) 42px}.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:16px}.card{background:linear-gradient(160deg,#142740ee,#0d1b2c);border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 14px 35px #0002;min-width:0}.span-12{grid-column:span 12}.span-8{grid-column:span 8}.span-7{grid-column:span 7}.span-6{grid-column:span 6}.span-5{grid-column:span 5}.span-4{grid-column:span 4}.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.kpi{padding:15px;border:1px solid #2a435e;border-radius:14px;background:#0a192a}.kpi label{display:block;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:1px}.kpi strong{font-size:26px;display:block;margin-top:7px;letter-spacing:-.7px}.kpi small{color:var(--muted)}
.cardhead{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:13px}.card h2{font-size:15px;margin:0;letter-spacing:.2px}.tag{font-size:10px;letter-spacing:1px;border:1px solid #35516d;padding:4px 8px;border-radius:7px;color:var(--blue);font-weight:800}.live-tag{color:var(--mint);border-color:#1b6558}.sim-tag{color:var(--amber);border-color:#7a6035}
svg{width:100%;height:auto;display:block;min-height:240px}.edge{stroke:#344c65;stroke-width:8;stroke-linecap:round;opacity:.95}.edge.up{stroke:var(--mint)}.edge.down{stroke:var(--red);stroke-dasharray:11 8}.edge.unknown{stroke:#66788d;stroke-dasharray:5 8}.edge.simbackup{stroke:var(--blue);stroke-width:10;filter:drop-shadow(0 0 5px #63b8ff55)}.node rect{fill:#152b44;stroke:#42627e;stroke-width:2}.node.host rect{fill:#123e3a;stroke:#36c99f}.node text{fill:#f2f7ff;text-anchor:middle;font-size:14px;font-weight:700}.edge-label{fill:#b6cce2;font-size:11px;text-anchor:middle;paint-order:stroke;stroke:#101f33;stroke-width:4px}
.legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:11px;margin-top:8px}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.scenarios{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.scenario{background:#0b1b2c;color:var(--text);border:1px solid #304b66;border-radius:12px;padding:12px;text-align:left;cursor:pointer;transition:.2s}.scenario:hover{border-color:var(--blue);transform:translateY(-1px)}.scenario b{display:block;font-size:12px}.scenario span{display:block;color:var(--muted);font-size:11px;margin-top:3px}.scenario.active{border-color:var(--amber);background:#302718}
.statebox{padding:14px;border-radius:12px;background:#0a1a2a;border:1px solid #2b455f;margin:12px 0}.statebox .big{font-size:18px;font-weight:850}.statebox p{margin:4px 0;color:var(--muted);font-size:12px}.statusdot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--mint);margin-right:6px}.statusdot.warn{background:var(--amber)}.statusdot.bad{background:var(--red)}
table{width:100%;border-collapse:collapse;font-size:12px}td,th{text-align:left;padding:10px 7px;border-bottom:1px solid #223a52}th{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.8px}td:last-child,th:last-child{text-align:right}.status-up{color:var(--mint);font-weight:800}.status-down{color:var(--red);font-weight:800}.status-unknown{color:var(--muted);font-weight:800}
canvas{width:100%;height:165px;display:block}.eventlog{display:flex;flex-direction:column;gap:9px}.event{display:flex;gap:10px;align-items:flex-start;font-size:12px}.event i{font-style:normal;min-width:23px;height:23px;border:1px solid #31516d;border-radius:8px;display:grid;place-items:center;color:var(--blue)}.event span{color:#c8d8e9}.footnote{color:var(--muted);font-size:11px;margin-top:13px}.smallprint{color:var(--muted);font-size:11px}.refresh{color:var(--muted);font-size:11px}#alert{display:none;background:#47232b;border:1px solid #8d4552;color:#ffdbe0;padding:10px;border-radius:10px;margin-bottom:14px}
@media(max-width:950px){.span-8,.span-7,.span-6,.span-5,.span-4{grid-column:span 12}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:460px){.kpi strong{font-size:21px}.scenarios{grid-template-columns:1fr}}
.topology-editor{margin-top:18px;padding-top:16px;border-top:1px solid #223a52}.topology-editor h3{margin:0;font-size:14px}
.editor-controls{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;margin-top:12px}.editor-field{display:flex;flex-direction:column;gap:4px;min-width:110px;flex:1}.editor-field label,.editor-check{color:var(--muted);font-size:11px}.editor-check{display:flex;align-items:center;gap:6px;padding-bottom:10px}
.editor-field input,.editor-field select{background:#0b1b2c;color:var(--text);border:1px solid #304b66;border-radius:9px;padding:8px 10px;font:inherit}
.editor-btn{background:#0b1b2c;color:var(--text);border:1px solid #304b66;border-radius:9px;padding:9px 13px;font:inherit;font-weight:700;cursor:pointer}.editor-btn:hover{border-color:var(--blue)}.editor-btn.primary{background:#14406a;border-color:var(--blue)}
.designer-svg{margin-top:12px;border:1px dashed #2b455f;border-radius:12px;background:#0a1a2a}.editor-message{margin-top:8px;font-size:12px;color:var(--mint)}.editor-list{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.connection-chip{font:inherit;font-size:11px;color:#c8d8e9;background:#0b1b2c;border:1px solid #31516d;border-radius:999px;padding:3px 10px}button.connection-chip{cursor:pointer}button.connection-chip:hover{border-color:var(--red);color:#fff}
.overlay{stroke:var(--blue);stroke-width:4;stroke-dasharray:3 11;stroke-linecap:round;fill:none;animation:flow 1s linear infinite;pointer-events:none}@keyframes flow{to{stroke-dashoffset:-14}}
button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--blue);outline-offset:2px}.kpi small{word-break:break-word}.stale{color:var(--amber)!important}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style></head>
<body>
<header><div class="brand"><div class="logo">✦</div><div><h1>Sentinel Twin <span style="color:var(--blue)">/</span> Autonomous Network Lab</h1><div class="subtitle">Digital Twin · Causal AI · Predictive Recovery · Self-Healing SDN</div></div></div><div class="pill"><span class="statusdot"></span>LIVE OBSERVABILITY <span style="color:#5c7895">/</span> <span id="clock">connecting…</span></div></header>
<main><div id="alert"></div>
<div class="grid">
<section class="card span-12"><div class="kpis">
<div class="kpi"><label>Telemetry observations</label><strong id="telemetryCount">—</strong><small id="dbState">Reading SQLite</small></div>
<div class="kpi"><label>Links up / total</label><strong id="linksUp">—</strong><small id="linksNote">Live OVS / Linux interfaces</small></div>
<div class="kpi"><label>Twin risk state</label><strong id="risk">LOW</strong><small id="twinState">Synchronized</small></div>
<div class="kpi"><label>Learning readiness</label><strong id="learningReady">—</strong><small id="learningNote">Verified feedback only</small></div>
</div></section>
<section class="card span-7"><div class="cardhead"><h2>01 / Live network topology</h2><span class="tag live-tag" id="topoTag">NETWORK STATUS</span></div>
<svg viewBox="0 0 780 420" role="img" aria-label="Live Mininet network topology"><g id="edges"></g><g id="overlay"></g><g id="nodes"></g></svg>
<div class="legend"><span><i class="dot" style="background:var(--mint)"></i>Interface up</span><span><i class="dot" style="background:var(--red)"></i>Interface down</span><span><i class="dot" style="background:#66788d"></i>Unknown / unavailable</span><span><i class="dot" style="background:var(--blue)"></i>Simulated reroute (twin only)</span></div>
<div class="footnote">This diagram shows actual OVS/Linux interface status only. Unknown means the interface could not be queried; it does not mean up. Twin scenarios are simulated separately.</div>
<div class="topology-editor" aria-labelledby="designerTitle">
 <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap"><h3 id="designerTitle">Topology designer</h3><span class="tag">VISUAL SANDBOX</span></div>
 <div class="smallprint" style="margin-top:6px">Design a topology independently. These edits do not create or modify Mininet/OVS links.</div>
 <div class="editor-controls">
  <div class="editor-field"><label for="designHosts">Hosts (1–12)</label><input id="designHosts" type="number" min="1" max="12" value="2"></div>
  <div class="editor-field"><label for="designSwitches">Switches (1–12)</label><input id="designSwitches" type="number" min="1" max="12" value="3"></div>
  <label class="editor-check"><input id="designAuto" type="checkbox" checked> Auto-connect</label><button id="buildDesign" class="editor-btn primary" type="button">Build design</button>
 </div>
 <div class="editor-controls">
  <div class="editor-field"><label for="designFrom">Connect from</label><select id="designFrom"></select></div>
  <div class="editor-field"><label for="designTo">Connect to</label><select id="designTo"></select></div>
  <button id="addDesignLink" class="editor-btn" type="button">Add connection</button>
  <button id="clearDesignLinks" class="editor-btn" type="button">Clear links</button>
  <button id="resetDesign" class="editor-btn" type="button">Reset design</button>
  <button id="deployDesign" class="editor-btn primary" type="button">▶ Run this network</button>
 </div>
 <svg id="designerSvg" class="designer-svg" viewBox="0 0 780 360" role="img" aria-label="User-designed network topology"><g id="designerEdges"></g><g id="designerNodes"></g></svg>
 <div id="designMessage" class="editor-message" role="status" aria-live="polite">Visual sandbox ready. Build a design or add a connection.</div>
 <div id="designStats" class="smallprint" style="margin-top:8px"></div><div id="designConnectionList" class="editor-list"></div>
</div></section>
<section class="card span-5"><div class="cardhead"><h2>02 / Scenario control room</h2><span class="tag sim-tag">TWIN ONLY</span></div>
<div class="smallprint">Choose a demonstration scenario. These buttons change the simulated twin state only; they do not alter Mininet links or execute controller commands.</div>
<div class="scenarios" style="margin-top:13px">
<button class="scenario active" data-scenario="normal"><b>◉ Normal network</b><span>Healthy state / no recovery</span></button>
<button class="scenario" data-scenario="congestion"><b>⌁ Congestion</b><span>Anomaly + causal hypothesis</span></button>
<button class="scenario" data-scenario="link_failure"><b>⤨ Link failure</b><span>Counterfactual alternate route</span></button>
<button class="scenario" data-scenario="recovery_failure"><b>↶ Recovery failure</b><span>Verification + rollback story</span></button>
</div>
<div class="statebox"><div class="cardhead" style="margin:0 0 8px"><span class="smallprint">TWIN STATE</span><span id="simMode" class="tag sim-tag">SIMULATION</span></div><div class="big" id="simTitle">Normal network</div><p id="simCause">No abnormal condition observed</p><div style="display:flex;justify-content:space-between;gap:10px;margin-top:12px"><div><span class="smallprint">DECISION</span><div id="simAction" style="font-weight:800;color:var(--blue)">NO ACTION</div></div><div style="text-align:right"><span class="smallprint">VERIFICATION</span><div id="simVerify" style="font-weight:800;color:var(--mint)">PASS</div></div></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px"><div style="border:1px solid #29415d;border-radius:10px;padding:10px"><span class="smallprint">TWIN PACKET LOSS</span><div id="simLoss" style="font-size:20px;font-weight:850">0%</div></div><div style="border:1px solid #29415d;border-radius:10px;padding:10px"><span class="smallprint">TWIN LATENCY</span><div id="simLatency" style="font-size:20px;font-weight:850">2.4 ms</div></div></div><div class="footnote">Scenario metrics are simulated twin values, not live measured network metrics.</div></div>
<div id="events" class="eventlog"></div></section>
<section class="card span-6"><div class="cardhead"><h2>03 / Live telemetry stream</h2><span class="tag live-tag">SQLITE</span></div><canvas id="chart" width="700" height="165"></canvas><div class="smallprint">Latest recorded ping packet-loss observations, where available. Historical records are not a live probe.</div><table style="margin-top:10px"><thead><tr><th>Time</th><th>Source / node</th><th>Port</th><th>Key metric</th></tr></thead><tbody id="telemetryRows"></tbody></table></section>
<section class="card span-6"><div class="cardhead"><h2>04 / Trust & safety monitor</h2><span class="tag">GUARDRAILS</span></div>
<div class="eventlog" id="trustItems"></div>
<div class="statebox"><div class="big">Autonomous action policy</div><p>Reject malformed telemetry. Validate route adjacency. Require explicit counterfactual feasibility. Record approvals and rejections. Live model promotion remains disabled until verified learning data is approved.</p></div>
<div class="smallprint">Security checks are code-level controls; this panel is not a claim of production-grade authentication or a penetration-test result.</div></section>
<section class="card span-12"><div class="cardhead"><h2>05 / Operator event timeline</h2><span class="refresh" id="lastUpdated">Waiting for first update…</span></div><div id="timeline" class="eventlog"><div class="event"><i>…</i><span>Connecting to live telemetry and interface probes.</span></div></div></section>
</div>
</main>
<script>
const $=id=>document.getElementById(id);
const num=v=>(v===null||v===undefined||v===""||typeof v==="boolean")?null:(Number.isFinite(Number(v))?Number(v):null);
const toMs=t=>{const n=num(t);if(n!==null)return n>1e11?n:n*1000;const p=Date.parse(t);return Number.isFinite(p)?p:null};
const fmtTime=t=>{const ms=toMs(t);return ms===null?"—":new Date(ms).toLocaleTimeString()};
const lossOf=r=>num(r&&r.metrics&&r.metrics.packet_loss_percent);
function metricText(r){const l=lossOf(r);if(l!==null)return{t:l+"%",bad:l>0};const m=Object.entries((r&&r.metrics)||{}).filter(([,v])=>num(v)!==null).slice(0,2);return m.length?{t:m.map(([k,v])=>k+"="+(+Number(v).toFixed(2))).join(", "),bad:null}:{t:"—",bad:null}}
const defaultNodes={h1:{x:75,y:205,w:86,h:48,label:"HOST h1",host:true},s1:{x:255,y:205,w:94,h:56,label:"SWITCH s1"},s2:{x:530,y:205,w:94,h:56,label:"SWITCH s2"},s3:{x:393,y:345,w:94,h:56,label:"SWITCH s3"},h2:{x:710,y:205,w:86,h:48,label:"HOST h2",host:true}};
const defaultEdges=[{id:"h1-s1",a:"h1",b:"s1"},{id:"s1-s2",a:"s1",b:"s2"},{id:"s1-s3",a:"s1",b:"s3"},{id:"s3-s2",a:"s3",b:"s2"},{id:"s2-h2",a:"s2",b:"h2"}];
let nodes=defaultNodes,edges=defaultEdges,netMode="mininet",lastStatusMap={};
const defaultSig=defaultEdges.map(e=>e.id).join(),NS="http://www.w3.org/2000/svg",edgeLayer=$("edges"),nodeLayer=$("nodes"),overlayLayer=$("overlay");
let topoSig=defaultSig;
function svg(tag,attrs){const el=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v));return el}
function buildTopology(){edgeLayer.replaceChildren();nodeLayer.replaceChildren();overlayLayer.replaceChildren();
 for(const e of edges){const a=nodes[e.a],b=nodes[e.b];if(!a||!b)continue;const ln=svg("line",{x1:a.x,y1:a.y,x2:b.x,y2:b.y,id:"edge-"+e.id,class:"edge unknown",style:"cursor:pointer"});ln.addEventListener("click",()=>toggleLink(e.id));edgeLayer.appendChild(ln);const t=svg("text",{x:(a.x+b.x)/2,y:(a.y+b.y)/2-11,id:"label-"+e.id,class:"edge-label"});t.textContent=e.id;edgeLayer.appendChild(t)}
 for(const [id,n] of Object.entries(nodes)){const g=svg("g",{class:"node"+(n.host?" host":""),transform:`translate(${n.x-n.w/2},${n.y-n.h/2})`});g.appendChild(svg("rect",{width:n.w,height:n.h,rx:13}));const t=svg("text",{x:n.w/2,y:n.h/2+5});t.textContent=n.label;g.appendChild(t);nodeLayer.appendChild(g)}}
function layoutFor(links){const ids=[...new Set(links.flatMap(l=>[l.a,l.b]))].sort((x,y)=>(x[0]===y[0]?0:x[0]==="h"?-1:1)||(parseInt(x.slice(1))-parseInt(y.slice(1))));
 const cols=Math.min(5,ids.length),rows=Math.ceil(ids.length/cols),m={};
 ids.forEach((id,i)=>{const r=Math.floor(i/cols),c=i%cols,rc=Math.min(cols,ids.length-r*cols),span=rc>1?620:0,host=id[0]==="h";m[id]={x:390-span/2+(rc>1?c*span/(rc-1):0),y:rows>1?60+r*(300/(rows-1)):205,w:host?86:94,h:host?48:56,label:(host?"HOST ":"SWITCH ")+id,host}});return m}
function syncTopology(links){const sig=links.map(l=>l.id).join();if(sig===topoSig)return;topoSig=sig;
 if(sig===defaultSig){nodes=defaultNodes;edges=defaultEdges}else{nodes=layoutFor(links);edges=links.map(l=>({id:l.id,a:l.a,b:l.b}))}buildTopology()}
buildTopology();
async function toggleLink(id){if(netMode!=="emulated")return;const down=lastStatusMap[id]!=="down";try{const r=await fetch("/api/link",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id,down})});const d=await r.json();if(!r.ok)throw Error(d.error||"request failed");addTimeline(down?"✕":"✓",`Link ${id} ${down?"failed":"restored"} in emulated network`);renderStatus(d)}catch(e){addTimeline("!",`Link change rejected: ${e.message}`)}}
function drawOverlay(sc){overlayLayer.replaceChildren();if(!(nodes.s1&&nodes.s2&&nodes.s3)||(sc!=="link_failure"&&sc!=="recovery_failure"))return;
 [["s1","s3"],["s3","s2"]].forEach(([x,y])=>{const a=nodes[x],b=nodes[y];overlayLayer.appendChild(svg("line",{x1:a.x,y1:a.y,x2:b.x,y2:b.y,class:"overlay"}))});
 const t=svg("text",{x:393,y:398,class:"edge-label"});t.textContent="simulated reroute via s3";overlayLayer.appendChild(t);
 if(sc==="link_failure"){const f=svg("text",{x:393,y:236,class:"edge-label",style:"fill:var(--red)"});f.textContent="✕ simulated failure s1–s2";overlayLayer.appendChild(f)}}
// Independent visual topology designer. It never changes the live Mininet/OVS network.
let designNodes={},designEdges=[],designNextLinkId=1;
const designNS="http://www.w3.org/2000/svg";
const designEdgeLayer=$("designerEdges"),designNodeLayer=$("designerNodes");
function designSvg(tag,attrs){const el=document.createElementNS(designNS,tag);Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v));return el}
function drawDesign(){
 designEdgeLayer.replaceChildren();designNodeLayer.replaceChildren();
 for(const edge of designEdges){
  const a=designNodes[edge.a],b=designNodes[edge.b];if(!a||!b)continue;
  designEdgeLayer.appendChild(designSvg("line",{x1:a.x,y1:a.y,x2:b.x,y2:b.y,id:"design-edge-"+edge.id,class:"edge"}));
  const label=designSvg("text",{x:(a.x+b.x)/2,y:(a.y+b.y)/2-8,class:"edge-label"});
  label.textContent=edge.a+"–"+edge.b;designEdgeLayer.appendChild(label);
 }
 for(const [id,n] of Object.entries(designNodes)){
  const g=designSvg("g",{class:"node"+(n.host?" host":""),transform:`translate(${n.x-n.w/2},${n.y-n.h/2})`});
  g.appendChild(designSvg("rect",{width:n.w,height:n.h,rx:10}));
  const label=designSvg("text",{x:n.w/2,y:n.h/2+4});label.textContent=id.toUpperCase();
  g.appendChild(label);designNodeLayer.appendChild(g);
 }
 const from=$("designFrom"),to=$("designTo"),oldFrom=from.value,oldTo=to.value,ids=Object.keys(designNodes);
 for(const select of [from,to])select.replaceChildren(...ids.map(id=>{const o=document.createElement("option");o.value=id;o.textContent=(designNodes[id].host?"Host ":"Switch ")+id;return o}));
 if(ids.includes(oldFrom))from.value=oldFrom;
 if(ids.includes(oldTo))to.value=oldTo;
 $("designConnectionList").replaceChildren(...designEdges.map(edge=>{const chip=document.createElement("button");chip.type="button";chip.className="connection-chip";chip.textContent=edge.a+" ↔ "+edge.b+" ✕";chip.title="Remove this connection";chip.addEventListener("click",()=>{designEdges=designEdges.filter(x=>x.id!==edge.id);drawDesign();$("designMessage").textContent=`Connection removed: ${edge.a} ↔ ${edge.b}.`});return chip}));
 if(!designEdges.length){const chip=document.createElement("span");chip.className="connection-chip";chip.textContent="No connections";$("designConnectionList").appendChild(chip)}
 const parent={};ids.forEach(i=>parent[i]=i);const find=x=>parent[x]===x?x:(parent[x]=find(parent[x]));
 designEdges.forEach(e=>{if(parent[e.a]!==undefined&&parent[e.b]!==undefined)parent[find(e.a)]=find(e.b)});
 const groups=new Set(ids.map(find)).size,extra=designEdges.length-(ids.length-groups);
 $("designStats").textContent=ids.length?(groups===1?"All devices connected":groups+" disconnected groups")+" · "+(extra>0?extra+" redundant link(s): loops give alternate paths":"no redundant links: one failure can split the network"):"";
}
function buildDesign(defaultLinks=false){
 const hostCount=Math.max(1,Math.min(12,Number.parseInt($("designHosts").value,10)||1));
 const switchCount=Math.max(1,Math.min(12,Number.parseInt($("designSwitches").value,10)||1));
 $("designHosts").value=hostCount;$("designSwitches").value=switchCount;
 designNodes={};designEdges=[];designNextLinkId=1;
 const devices=[];
 for(let i=1;i<=hostCount;i++)devices.push({id:"h"+i,host:true,w:72,h:42});
 for(let i=1;i<=switchCount;i++)devices.push({id:"s"+i,host:false,w:82,h:46});
 const cols=Math.min(5,devices.length),rows=Math.ceil(devices.length/cols);
 devices.forEach((d,i)=>{
  const row=Math.floor(i/cols),col=i%cols,rowCount=Math.min(cols,devices.length-row*cols);
  const span=rowCount>1?670:0;designNodes[d.id]={...d,x:390-span/2+(rowCount>1?col*span/(rowCount-1):0),y:rows>1?45+row*(270/(rows-1)):180};
 });
 if(defaultLinks){
  for(let i=1;i<=hostCount;i++){
   const switchId="s"+Math.min(i,switchCount);
   designEdges.push({id:"d"+designNextLinkId++,a:"h"+i,b:switchId});
  }
  for(let i=1;i<switchCount;i++)designEdges.push({id:"d"+designNextLinkId++,a:"s"+i,b:"s"+(i+1)});
 }
 drawDesign();
 $("designMessage").textContent=`Design created: ${hostCount} host(s), ${switchCount} switch(es), ${designEdges.length} connection(s). Visual only.`;
}
function addDesignConnection(){
 const a=$("designFrom").value,b=$("designTo").value;
 if(!a||!b){$("designMessage").textContent="Add at least one host or switch before creating connections.";return}
 if(a===b){$("designMessage").textContent="A device cannot connect to itself.";return}
 if(designEdges.some(e=>(e.a===a&&e.b===b)||(e.a===b&&e.b===a))){$("designMessage").textContent="That connection already exists.";return}
 designEdges.push({id:"d"+designNextLinkId++,a,b});drawDesign();
 $("designMessage").textContent=`Connection added: ${a} ↔ ${b}. Total connections: ${designEdges.length}.`;
}
$("buildDesign").addEventListener("click",()=>buildDesign($("designAuto").checked));
$("addDesignLink").addEventListener("click",addDesignConnection);
$("clearDesignLinks").addEventListener("click",()=>{designEdges=[];drawDesign();$("designMessage").textContent="All visual connections cleared. Devices are unchanged."});
$("resetDesign").addEventListener("click",()=>{ $("designHosts").value=2;$("designSwitches").value=3;buildDesign(true);});
buildDesign(true);
$("deployDesign").addEventListener("click",async()=>{try{const r=await fetch("/api/design",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({nodes:Object.keys(designNodes),edges:designEdges.map(e=>[e.a,e.b])})});const d=await r.json();if(!r.ok)throw Error(d.error||"request failed");$("designMessage").textContent=`Network running: ${Object.keys(designNodes).length} devices, ${designEdges.length} links. See the live topology above.`;addTimeline("▶","Designed network deployed to the emulated runtime");renderStatus(d)}catch(e){$("designMessage").textContent="Cannot run design: "+e.message}});
let lastEventId=null, timelineItems=[];
function addTimeline(icon,msg){timelineItems.unshift({icon,msg,at:new Date().toLocaleTimeString()});timelineItems=timelineItems.slice(0,12);$("timeline").replaceChildren(...timelineItems.map(x=>{const d=document.createElement("div");d.className="event";const i=document.createElement("i");i.textContent=x.icon;const s=document.createElement("span");s.textContent=`${x.at} · ${x.msg}`;d.append(i,s);return d}))}
function renderEvents(items){$("events").replaceChildren(...items.map((x,i)=>{const d=document.createElement("div");d.className="event";const ic=document.createElement("i");ic.textContent=String(i+1).padStart(2,"0");const sp=document.createElement("span");sp.textContent=x;d.append(ic,sp);return d}))}
let chartRows=[];
function drawChart(rows){chartRows=rows||chartRows;const c=$("chart"),dpr=window.devicePixelRatio||1,W=c.clientWidth||700,H=165;
 if(c.width!==Math.round(W*dpr)||c.height!==Math.round(H*dpr)){c.width=Math.round(W*dpr);c.height=Math.round(H*dpr)}
 const ctx=c.getContext("2d");ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,W,H);ctx.font="10px sans-serif";ctx.textBaseline="middle";
 const L=36,R=10,T=12,B=14;
 for(let i=0;i<=2;i++){const y=T+i*(H-T-B)/2;ctx.strokeStyle="#29415d";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(W-R,y);ctx.stroke();ctx.fillStyle="#8fa8c4";ctx.textAlign="right";ctx.fillText((100-i*50)+"%",L-6,y)}
 const pts=chartRows.slice().reverse().map(lossOf).filter(v=>v!==null);
 if(!pts.length){ctx.fillStyle="#8fa8c4";ctx.font="13px sans-serif";ctx.textAlign="left";ctx.fillText("No parseable ping-loss samples yet",L+8,H/2);return}
 const step=(W-L-R)/Math.max(1,pts.length-1),X=i=>pts.length===1?L+(W-L-R)/2:L+i*step,Y=v=>H-B-(Math.min(100,v)/100)*(H-T-B);
 ctx.strokeStyle="#47e6ad";ctx.lineWidth=2.5;ctx.lineJoin="round";ctx.beginPath();pts.forEach((v,i)=>i?ctx.lineTo(X(i),Y(v)):ctx.moveTo(X(i),Y(v)));ctx.stroke();
 pts.forEach((v,i)=>{ctx.fillStyle=v>0?"#ff687d":"#47e6ad";ctx.beginPath();ctx.arc(X(i),Y(v),3.5,0,Math.PI*2);ctx.fill()})}
window.addEventListener("resize",()=>drawChart());
function renderStatus(d){$("clock").textContent=new Date(d.server_time*1000).toLocaleTimeString();const live=d.live,sim=d.simulation,tele=live.telemetry;
$("telemetryCount").textContent=Number(tele.count||0).toLocaleString();$("dbState").textContent=`SQLite: ${tele.database}`+(tele.error?` — ${tele.error}`:"");$("linksUp").textContent=`${live.up_links} / ${live.links.length}`;$("linksNote").textContent=`${live.down_links} down · ${live.unknown_links} unknown`+((d.network||{}).mode==="emulated"?" · emulated":"");
$("risk").textContent=sim.risk;$("risk").style.color=sim.risk==="CRITICAL"?"var(--red)":sim.risk==="HIGH"?"var(--amber)":"var(--mint)";$("twinState").textContent=sim.twin;
const lr=d.learning||{};if(lr.source==="demo-session"){const c=lr.demo_counts||{},m=lr.minimum_per_class||5,h=c.healthy||0,f=c.fault||0;$("learningReady").textContent=lr.ready_for_training?"READY":`${Math.min(h,m)+Math.min(f,m)} / ${2*m}`;$("learningNote").textContent=`Demo samples · healthy ${h}/${m} · fault ${f}/${m}`}
else{$("learningReady").textContent=lr.ready_for_training?"READY":(lr.status==="unavailable"||lr.error?"CHECK":"GATED");$("learningNote").textContent=lr.error?`Feedback check error: ${lr.error}`:`${lr.eligible_samples??0} eligible · need ${lr.minimum_per_class??5}/class`}
syncTopology(live.links);netMode=(d.network||{}).mode||"mininet";
$("topoTag").textContent=netMode==="emulated"?"EMULATED NETWORK · CLICK A LINK TO FAIL/RESTORE":"ACTUAL OVS STATUS";
const status=Object.fromEntries(live.links.map(x=>[x.id,x.status]));lastStatusMap=status;const linkInfo=Object.fromEntries(live.links.map(x=>[x.id,x]));
 for(const e of edges){const edgeEl=$("edge-"+e.id);if(edgeEl){const st=status[e.id]||"unknown";edgeEl.setAttribute("class","edge "+st);const tt=svg("title",{});const info=linkInfo[e.id];const details=info?(info.port_states||[]).map(p=>`${p.port}: ${p.status}`).join(", "):"";tt.textContent=`${e.id}: ${st}`+(details?` · ${details}`:info?` · ports: ${(info.ports||[]).join(", ")}`:" · no live interface evidence");edgeEl.replaceChildren(tt);const lb=$("label-"+e.id);if(lb)lb.textContent=e.id+(st==="down"?" ✕":st==="unknown"?" ?":"")}}
drawOverlay(sim.scenario);
$("simTitle").textContent=sim.title;$("simCause").textContent=sim.cause;$("simAction").textContent=sim.action;$("simVerify").textContent=sim.verification;$("simVerify").style.color=(sim.scenario==="normal"||sim.scenario==="link_failure")?"var(--mint)":"var(--amber)";$("simMode").textContent=sim.mode;$("simLoss").textContent=`${Number(sim.packet_loss_percent).toFixed(1)}%`;$("simLatency").textContent=`${Number(sim.latency_ms).toFixed(1)} ms`;
document.querySelectorAll(".scenario").forEach(b=>{const on=b.dataset.scenario===sim.scenario;b.classList.toggle("active",on);b.setAttribute("aria-pressed",on)});
renderEvents(sim.events||[]);
$("telemetryRows").replaceChildren(...(tele.latest.length?tele.latest.slice(0,8):[null]).map(r=>{const tr=document.createElement("tr"),m=r?metricText(r):null;const vals=r?[fmtTime(r.timestamp),`${r.source} / ${r.node}`,r.port||"—",m.t]:["No telemetry rows yet","","",""];vals.forEach((v,i)=>{const td=document.createElement("td");td.textContent=v;if(i===3&&m&&m.bad!==null)td.className=m.bad?"status-down":"status-up";tr.appendChild(td)});return tr}));
drawChart(tele.latest.filter(r=>r.source==="ping"));
const trust=[["✓","Malformed / non-finite telemetry is rejected at ingestion"],["✓","Controller validates discovered route adjacency"],["✓","Unknown actions and infeasible reroutes are denied"],["✓","Security decisions are appended to JSONL audit trail"],["!","Training remains gated until independent feedback is approved"]];
$("trustItems").replaceChildren(...trust.map(([icon,msg])=>{const d=document.createElement("div");d.className="event";const i=document.createElement("i");i.textContent=icon;i.style.color=icon==="!"?"var(--amber)":"var(--mint)";const s=document.createElement("span");s.textContent=msg;d.append(i,s);return d}));
if(lastEventId!==sim.event_id){const evId=lastEventId=sim.event_id;addTimeline("✦",`Twin scenario selected: ${sim.title}`);(sim.events||[]).forEach((e,i)=>setTimeout(()=>{if(lastEventId===evId)addTimeline("›",e)},(i+1)*650))}
$("lastUpdated").textContent=`Live refresh · ${new Date().toLocaleTimeString()}`;
}
let pollSeq=0,pollTimer=null,failures=0;
function schedule(){clearTimeout(pollTimer);pollTimer=setTimeout(poll,document.hidden?10000:Math.min(2000*2**Math.min(failures,3),15000))}
async function poll(){const my=++pollSeq;try{const r=await fetch("/api/status",{cache:"no-store"});if(!r.ok)throw Error("HTTP "+r.status);const d=await r.json();if(my!==pollSeq)return;failures=0;$("alert").style.display="none";$("lastUpdated").classList.remove("stale");renderStatus(d)}catch(e){if(my!==pollSeq)return;failures++;$("alert").style.display="block";$("alert").textContent="Dashboard API unavailable: "+e.message+" — retrying…";$("clock").textContent="offline";$("lastUpdated").classList.add("stale")}finally{schedule()}}
async function chooseScenario(name){++pollSeq;try{const r=await fetch("/api/scenario",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scenario:name})});const d=await r.json();if(!r.ok)throw Error(d.error||"request failed");renderStatus(d)}catch(e){addTimeline("!",`Scenario rejected: ${e.message}`)}}
document.querySelectorAll(".scenario").forEach(b=>b.addEventListener("click",()=>chooseScenario(b.dataset.scenario)));
document.addEventListener("visibilitychange",()=>{if(!document.hidden)poll()});poll();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "SentinelTwinDemo/2.0"

    def _send(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _host_ok(self) -> bool:
        """Reject unexpected Host headers (blocks DNS-rebinding against loopback)."""
        try:
            hostname = urlparse("//" + self.headers.get("Host", "")).hostname
        except ValueError:
            hostname = None
        if hostname in {"127.0.0.1", "::1", "localhost"}:
            return True
        self._send(403, b'{"error":"unexpected Host header"}', "application/json")
        return False

    def do_GET(self):
        if not self._host_ok():
            return
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/status":
            try:
                payload = json.dumps(get_status(), allow_nan=False).encode()
            except Exception as exc:  # keep the dashboard alive if any probe misbehaves
                self._send(500, json.dumps({"error": f"status failed: {exc}"}).encode(), "application/json")
            else:
                self._send(200, payload, "application/json")
        elif path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
        elif path == "/health":
            self._send(200, b'{"status":"ok"}', "application/json")
        else:
            self._send(404, b'{"error":"not found"}', "application/json")

    def do_POST(self):
        if not self._host_ok():
            return
        path = urlparse(self.path).path
        if path not in ("/api/scenario", "/api/design", "/api/link"):
            self._send(404, b'{"error":"not found"}', "application/json")
            return
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if origin and urlparse(origin).netloc != host:
            self._send(403, b'{"error":"cross-origin request rejected"}', "application/json")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 16384:
                raise ValueError("invalid request size")
            body = json.loads(self.rfile.read(length))
            if path == "/api/design":
                deploy_design(body)
                result = get_status()
            elif path == "/api/link":
                if not isinstance(body, dict):
                    raise ValueError("invalid body")
                set_link(body.get("id"), bool(body.get("down")))
                result = get_status()
            else:
                name = body.get("scenario") if isinstance(body, dict) else None
                result = set_scenario(name)
            self._send(200, json.dumps(result, allow_nan=False).encode(), "application/json")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send(400, json.dumps({"error": str(exc)}).encode(), "application/json")
        except Exception as exc:
            self._send(500, json.dumps({"error": f"server error: {exc}"}).encode(), "application/json")

    def log_message(self, fmt, *args):
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (loopback recommended)")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        parser.error("dashboard is designed for loopback only; remote binding is disabled")
    if ":" in args.host:
        ThreadingHTTPServer.address_family = socket.AF_INET6
    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        parser.exit(1, f"Cannot listen on {args.host}:{args.port} ({exc}).\nTry: python {Path(__file__).name} --port {args.port + 1}\n")
    print(f"Sentinel Twin dashboard: http://{args.host}:{args.port}")
    print(f"Project root: {PROJECT_ROOT}")
    print("LIVE panel reads actual OVS/Linux interface state and SQLite. Scenario controls are simulation-only.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
