#!/usr/bin/env python3
"""Creative live dashboard for the digital twin + self-healing network project.

The dashboard polls actual SQLite/OVS status. Scenario buttons operate only on
an in-memory twin simulation and never execute shell commands or change Mininet.
Bind to loopback by default.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]


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


def interface_status(name: str) -> str:
    value = run_command(["ovs-vsctl", "get", "Interface", name, "link_state"])
    if value:
        value = value.strip('"').lower()
        if value in ("up", "down"):
            return value
    value = run_command(["ip", "-o", "link", "show", "dev", name])
    if not value:
        return "unknown"
    flags = value.split(":", 2)[1] if value.count(":") >= 2 else ""
    if "UP" not in flags or "LOWER_UP" not in value:
        return "down"
    return "up"


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


def live_links() -> list[dict]:
    results = []
    for edge in current_edges():
        states = [interface_status(port) for port in edge["ports"]]
        status = "down" if "down" in states else "up" if all(x == "up" for x in states) else "unknown"
        results.append({**edge, "status": status})
    return results


def _normalize_metrics(raw: str) -> dict:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    if isinstance(value, dict) and isinstance(value.get("metrics"), dict):
        return value["metrics"]
    return value if isinstance(value, dict) else {}


def live_telemetry(limit: int = 30) -> dict:
    if not DB_PATH.exists():
        return {"database": "missing", "count": 0, "latest": [], "error": f"Database not found: {DB_PATH}"}
    try:
        with closing(sqlite3.connect(DB_PATH, timeout=1.0)) as conn:
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
    except sqlite3.Error as exc:
        return {"database": "error", "count": 0, "latest": [], "error": str(exc)}


def learning_status() -> dict:
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
        "live": {"links": links, "up_links": sum(x["status"] == "up" for x in links), "down_links": sum(x["status"] == "down" for x in links), "unknown_links": sum(x["status"] == "unknown" for x in links), "telemetry": telemetry},
        "simulation": sim,
        "learning": learning_status(),
    }


def set_scenario(name: str) -> dict:
    if name not in SIMULATION_SCENARIOS:
        raise ValueError(f"scenario must be one of: {', '.join(SIMULATION_SCENARIOS)}")
    with _STATE_LOCK:
        _SIM_STATE.update({"scenario": name, "started_at": time.time(), "event_id": _SIM_STATE["event_id"] + 1})
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
<section class="card span-7"><div class="cardhead"><h2>01 / Live network topology</h2><span class="tag live-tag">ACTUAL OVS STATUS</span></div>
<svg viewBox="0 0 780 420" role="img" aria-label="Live Mininet network topology"><g id="edges"></g><g id="nodes"></g></svg>
<div class="legend"><span><i class="dot" style="background:var(--mint)"></i>Interface up</span><span><i class="dot" style="background:var(--red)"></i>Interface down</span><span><i class="dot" style="background:#66788d"></i>Unknown / unavailable</span><span><i class="dot" style="background:var(--blue)"></i>Simulated alternate path</span></div>
<div class="footnote">The live panel reads interface state from Open vSwitch / Linux. Unknown means the interface could not be queried; it does not mean up.</div></section>
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
<section class="card span-6"><div class="cardhead"><h2>03 / Live telemetry stream</h2><span class="tag live-tag">SQLITE</span></div><canvas id="chart" width="700" height="165"></canvas><div class="smallprint">Latest recorded ping packet-loss observations, where available. Historical records are not a live probe.</div><table style="margin-top:10px"><thead><tr><th>Time</th><th>Source / node</th><th>Port</th><th>Loss</th></tr></thead><tbody id="telemetryRows"></tbody></table></section>
<section class="card span-6"><div class="cardhead"><h2>04 / Trust & safety monitor</h2><span class="tag">GUARDRAILS</span></div>
<div class="eventlog" id="trustItems"></div>
<div class="statebox"><div class="big">Autonomous action policy</div><p>Reject malformed telemetry. Validate route adjacency. Require explicit counterfactual feasibility. Record approvals and rejections. Live model promotion remains disabled until verified learning data is approved.</p></div>
<div class="smallprint">Security checks are code-level controls; this panel is not a claim of production-grade authentication or a penetration-test result.</div></section>
<section class="card span-12"><div class="cardhead"><h2>05 / Operator event timeline</h2><span class="refresh" id="lastUpdated">Waiting for first update…</span></div><div id="timeline" class="eventlog"><div class="event"><i>…</i><span>Connecting to live telemetry and interface probes.</span></div></div></section>
</div>
</main>
<script>
const $=id=>document.getElementById(id);
const nodes={h1:{x:75,y:205,w:86,h:48,label:"HOST h1",host:true},s1:{x:255,y:205,w:94,h:56,label:"SWITCH s1"},s2:{x:530,y:205,w:94,h:56,label:"SWITCH s2"},s3:{x:393,y:345,w:94,h:56,label:"SWITCH s3"},h2:{x:710,y:205,w:86,h:48,label:"HOST h2",host:true}};
const edges=[{id:"h1-s1",a:"h1",b:"s1"},{id:"s1-s2",a:"s1",b:"s2"},{id:"s1-s3",a:"s1",b:"s3"},{id:"s3-s2",a:"s3",b:"s2"},{id:"s2-h2",a:"s2",b:"h2"}];
const NS="http://www.w3.org/2000/svg",edgeLayer=$("edges"),nodeLayer=$("nodes");
function svg(tag,attrs){const el=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v));return el}
for(const e of edges){const a=nodes[e.a],b=nodes[e.b];edgeLayer.appendChild(svg("line",{x1:a.x,y1:a.y,x2:b.x,y2:b.y,id:"edge-"+e.id,class:"edge unknown"}));const t=svg("text",{x:(a.x+b.x)/2,y:(a.y+b.y)/2-11,id:"label-"+e.id,class:"edge-label"});t.textContent=e.id;edgeLayer.appendChild(t)}
for(const [id,n] of Object.entries(nodes)){const g=svg("g",{class:"node"+(n.host?" host":""),transform:`translate(${n.x-n.w/2},${n.y-n.h/2})`});g.appendChild(svg("rect",{width:n.w,height:n.h,rx:13}));const t=svg("text",{x:n.w/2,y:n.h/2+5});t.textContent=n.label;g.appendChild(t);nodeLayer.appendChild(g)}
let lastEventId=null, timelineItems=[];
function addTimeline(icon,msg){timelineItems.unshift({icon,msg,at:new Date().toLocaleTimeString()});timelineItems=timelineItems.slice(0,8);$("timeline").replaceChildren(...timelineItems.map(x=>{const d=document.createElement("div");d.className="event";const i=document.createElement("i");i.textContent=x.icon;const s=document.createElement("span");s.textContent=`${x.at} · ${x.msg}`;d.append(i,s);return d}))}
function renderEvents(items){$("events").replaceChildren(...items.map((x,i)=>{const d=document.createElement("div");d.className="event";const ic=document.createElement("i");ic.textContent=String(i+1).padStart(2,"0");const sp=document.createElement("span");sp.textContent=x;d.append(ic,sp);return d}))}
function drawChart(rows){const c=$("chart"),ctx=c.getContext("2d"),w=c.width,h=c.height;ctx.clearRect(0,0,w,h);ctx.strokeStyle="#29415d";ctx.lineWidth=1;for(let i=0;i<4;i++){const y=15+i*(h-30)/3;ctx.beginPath();ctx.moveTo(30,y);ctx.lineTo(w-8,y);ctx.stroke()}const points=rows.slice().reverse().map(r=>Number(r.metrics?.packet_loss_percent)).filter(Number.isFinite);if(!points.length){ctx.fillStyle="#8fa8c4";ctx.font="14px sans-serif";ctx.fillText("No parseable ping-loss samples yet",30,80);return}const max=Math.max(100,...points),step=(w-50)/Math.max(1,points.length-1);ctx.strokeStyle="#47e6ad";ctx.lineWidth=3;ctx.beginPath();points.forEach((v,i)=>{const x=30+i*step,y=h-15-(v/max)*(h-30);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke();points.forEach((v,i)=>{const x=30+i*step,y=h-15-(v/max)*(h-30);ctx.fillStyle=v>0?"#ff687d":"#47e6ad";ctx.beginPath();ctx.arc(x,y,3,0,Math.PI*2);ctx.fill()})}
function renderStatus(d){$("clock").textContent=new Date(d.server_time*1000).toLocaleTimeString();const live=d.live,sim=d.simulation,tele=live.telemetry;
$("telemetryCount").textContent=Number(tele.count||0).toLocaleString();$("dbState").textContent=`SQLite: ${tele.database}`;$("linksUp").textContent=`${live.up_links} / ${live.links.length}`;$("linksNote").textContent=`${live.down_links} down · ${live.unknown_links} unknown`;
$("risk").textContent=sim.risk;$("risk").style.color=sim.risk==="CRITICAL"?"var(--red)":sim.risk==="HIGH"?"var(--amber)":"var(--mint)";$("twinState").textContent=sim.twin;
const lr=d.learning||{};$("learningReady").textContent=lr.ready_for_training?"READY":"GATED";$("learningNote").textContent=`${lr.eligible_samples??0} eligible · need ${lr.minimum_per_class??5}/class`;
const status=Object.fromEntries(live.links.map(x=>[x.id,x.status]));const primary=["h1-s1","s1-s2","s2-h2"],backup=["h1-s1","s1-s3","s3-s2","s2-h2"];
for(const e of edges){let cl="edge "+(status[e.id]||"unknown");if(sim.scenario==="link_failure"&&backup.includes(e.id)&&!["s1-s2"].includes(e.id))cl="edge simbackup";if(sim.scenario==="recovery_failure"&&backup.includes(e.id))cl="edge simbackup";$("edge-"+e.id).setAttribute("class",cl)}
$("linkRows")?.replaceChildren();
$("simTitle").textContent=sim.title;$("simCause").textContent=sim.cause;$("simAction").textContent=sim.action;$("simVerify").textContent=sim.verification;$("simMode").textContent=sim.mode;$("simLoss").textContent=`${Number(sim.packet_loss_percent).toFixed(1)}%`;$("simLatency").textContent=`${Number(sim.latency_ms).toFixed(1)} ms`;
document.querySelectorAll(".scenario").forEach(b=>b.classList.toggle("active",b.dataset.scenario===sim.scenario));
renderEvents(sim.events||[]);
$("telemetryRows").replaceChildren(...tele.latest.slice(0,5).map(r=>{const tr=document.createElement("tr");const vals=[new Date(r.timestamp*1000).toLocaleTimeString(),`${r.source} / ${r.node}`,r.port||"—",Number.isFinite(Number(r.metrics?.packet_loss_percent))?`${r.metrics.packet_loss_percent}%`:"—"];vals.forEach((v,i)=>{const td=document.createElement("td");td.textContent=v;if(i===3&&String(v)!=="—")td.className=Number(r.metrics.packet_loss_percent)>0?"status-down":"status-up";tr.appendChild(td)});return tr}));
drawChart(tele.latest.filter(r=>r.source==="ping"));
const trust=[["✓","Malformed / non-finite telemetry is rejected at ingestion"],["✓","Controller validates discovered route adjacency"],["✓","Unknown actions and infeasible reroutes are denied"],["✓","Security decisions are appended to JSONL audit trail"],["!","Training remains gated until independent feedback is approved"]];
$("trustItems").replaceChildren(...trust.map(([icon,msg])=>{const d=document.createElement("div");d.className="event";const i=document.createElement("i");i.textContent=icon;i.style.color=icon==="!"?"var(--amber)":"var(--mint)";const s=document.createElement("span");s.textContent=msg;d.append(i,s);return d}));
if(lastEventId!==sim.event_id){lastEventId=sim.event_id;addTimeline("✦",`Twin scenario selected: ${sim.title}`);(sim.events||[]).forEach(e=>addTimeline("›",e))}
$("lastUpdated").textContent=`Live refresh · ${new Date().toLocaleTimeString()}`;
}
async function poll(){try{const r=await fetch("/api/status",{cache:"no-store"});if(!r.ok)throw Error("HTTP "+r.status);const d=await r.json();$("alert").style.display="none";renderStatus(d)}catch(e){$("alert").style.display="block";$("alert").textContent="Dashboard API unavailable: "+e.message}}
async function chooseScenario(name){try{const r=await fetch("/api/scenario",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scenario:name})});const d=await r.json();if(!r.ok)throw Error(d.error||"request failed");renderStatus(d)}catch(e){addTimeline("!",`Scenario rejected: ${e.message}`)}}
document.querySelectorAll(".scenario").forEach(b=>b.addEventListener("click",()=>chooseScenario(b.dataset.scenario)));
poll();setInterval(poll,2000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "SentinelTwinDemo/1.0"

    def _send(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/status":
            self._send(200, json.dumps(get_status(), allow_nan=False).encode(), "application/json")
        elif path == "/health":
            self._send(200, b'{"status":"ok"}', "application/json")
        else:
            self._send(404, b'{"error":"not found"}', "application/json")

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/scenario":
            self._send(404, b'{"error":"not found"}', "application/json")
            return
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if origin and urlparse(origin).netloc != host:
            self._send(403, b'{"error":"cross-origin request rejected"}', "application/json")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 4096:
                raise ValueError("invalid request size")
            body = json.loads(self.rfile.read(length))
            name = body.get("scenario") if isinstance(body, dict) else None
            result = set_scenario(name)
            self._send(200, json.dumps(result, allow_nan=False).encode(), "application/json")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send(400, json.dumps({"error": str(exc)}).encode(), "application/json")

    def log_message(self, fmt, *args):
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (loopback recommended)")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        parser.error("dashboard is designed for loopback only; remote binding is disabled")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Sentinel Twin dashboard: http://{args.host}:{args.port}")
    print(f"Project root: {PROJECT_ROOT}")
    print("LIVE panel reads OVS/Linux and SQLite. Scenario controls are simulation-only.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
