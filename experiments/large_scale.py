"""Reproducible graph-scale experiments for the digital-twin routing logic.

This is an algorithmic graph simulation, not a claim that Mininet ran at these
sizes. Live emulation results must be collected separately.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from collections import deque
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "reports" / "results"


def make_redundant_graph(node_count: int) -> dict[str, set[str]]:
    if isinstance(node_count, bool) or not isinstance(node_count, int) or node_count < 3:
        raise ValueError("node_count must be an integer >= 3")
    graph = {f"n{i}": set() for i in range(node_count)}
    # Ring keeps a second route available after any single ring-edge failure.
    for i in range(node_count):
        a, b = f"n{i}", f"n{(i + 1) % node_count}"
        graph[a].add(b); graph[b].add(a)
    # Add deterministic long-range chords to mimic a mesh-like fabric.
    for i in range(node_count // 2):
        a, b = f"n{i}", f"n{(i + node_count // 2) % node_count}"
        if a != b:
            graph[a].add(b); graph[b].add(a)
    return graph


def shortest_path(graph: dict[str, set[str]], source: str, target: str,
                  failed_edges: Iterable[tuple[str, str]] = ()) -> list[str] | None:
    blocked = {frozenset(edge) for edge in failed_edges}
    queue = deque([(source, [source])])
    visited = {source}
    while queue:
        node, path = queue.popleft()
        if node == target:
            return path
        for neighbor in sorted(graph.get(node, set())):
            if frozenset((node, neighbor)) in blocked or neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append((neighbor, path + [neighbor]))
    return None


def run_scale_experiments(sizes=(5, 10, 20, 50, 100), repetitions=10) -> list[dict]:
    if repetitions < 1:
        raise ValueError("repetitions must be >= 1")
    results = []
    for size in sizes:
        graph = make_redundant_graph(int(size))
        source, target = "n0", f"n{int(size)-1}"
        failed_edge = ("n0", "n1")
        for trial in range(1, repetitions + 1):
            started = time.perf_counter()
            path = shortest_path(graph, source, target, [failed_edge])
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            results.append({
                "experiment_type": "algorithmic_graph_simulation",
                "node_count": int(size),
                "edge_count": sum(len(v) for v in graph.values()) // 2,
                "trial": trial,
                "failed_edge": f"{failed_edge[0]}-{failed_edge[1]}",
                "reachable_after_failure": path is not None,
                "recovered_path_hops": len(path) - 1 if path else None,
                "route_computation_ms": round(elapsed_ms, 6),
                "live_mininet": False,
            })
    return results


def write_results(results: list[dict], output_dir: str | Path = RESULTS_DIR) -> tuple[Path, Path]:
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "phase15_scale_trials.csv"
    json_path = out / "phase15_scale_summary.json"
    if results:
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(results[0]))
            writer.writeheader(); writer.writerows(results)
    by_size = {}
    for row in results:
        entry = by_size.setdefault(str(row["node_count"]), {"trials": 0, "reachable": 0, "route_ms": []})
        entry["trials"] += 1
        entry["reachable"] += int(row["reachable_after_failure"])
        entry["route_ms"].append(row["route_computation_ms"])
    summary = {
        "experiment_type": "algorithmic_graph_simulation",
        "not_live_mininet": True,
        "results_by_node_count": {
            size: {
                "trials": v["trials"],
                "reachable_trials": v["reachable"],
                "reachability_rate": v["reachable"] / v["trials"] if v["trials"] else None,
                "mean_route_computation_ms": sum(v["route_ms"]) / len(v["route_ms"]) if v["route_ms"] else None,
            } for size, v in by_size.items()
        },
        "interpretation": "Synthetic graph algorithm timings only; do not report as network recovery time.",
    }
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return csv_path, json_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", default="5,10,20,50,100")
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--output-dir", default=str(RESULTS_DIR))
    args = parser.parse_args(argv)
    sizes = [int(item.strip()) for item in args.sizes.split(",") if item.strip()]
    results = run_scale_experiments(sizes, args.repetitions)
    paths = write_results(results, args.output_dir)
    print(f"Trials: {len(results)}")
    for path in paths: print(f"Wrote: {path}")
    for size in sorted({row["node_count"] for row in results}):
        subset = [r for r in results if r["node_count"] == size]
        print(f"{size} nodes: {sum(r['reachable_after_failure'] for r in subset)}/{len(subset)} reachable")
    print("NOTE: graph simulation only; live Mininet scale is not claimed.")


if __name__ == "__main__":
    main()
