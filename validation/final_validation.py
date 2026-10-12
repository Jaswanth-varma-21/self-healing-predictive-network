"""Phase 16 software validation and evidence manifest.

Live network tests are explicitly marked NOT RUN unless their results are
provided as evidence. This prevents a unit-test pass from masquerading as an
end-to-end Mininet experiment.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS = PROJECT_ROOT / "reports" / "results"


def check_project_files() -> dict:
    required = [
        "sdn_controller/self_healing_controller.py",
        "sdn_controller/topologies/redundant_topology.py",
        "digital_twin/digital_twin.py",
        "causal_ai/intervention_evidence.py",
        "failure_prediction/continuous_learning.py",
        "security/trust_layer.py",
        "evaluation/framework.py",
        "experiments/large_scale.py",
        "demo/live_demo.py",
        "README.md",
    ]
    missing = [item for item in required if not (PROJECT_ROOT / item).is_file()]
    return {"name": "required_project_files", "status": "PASS" if not missing else "FAIL", "missing": missing}


def check_database() -> dict:
    path = PROJECT_ROOT / "telemetry" / "data" / "telemetry.db"
    if not path.exists():
        return {"name": "telemetry_database", "status": "NOT_AVAILABLE", "path": str(path)}
    try:
        with closing(sqlite3.connect(path)) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            count = conn.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0] if "telemetry" in tables else None
        return {"name": "telemetry_database", "status": "PASS" if "telemetry" in tables else "PARTIAL", "tables": sorted(tables), "telemetry_rows": count}
    except sqlite3.Error as exc:
        return {"name": "telemetry_database", "status": "FAIL", "error": str(exc)}


def run_unit_tests() -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, timeout=180,
    )
    return {
        "name": "unit_tests",
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "return_code": proc.returncode,
        "output_tail": (proc.stdout + "\n" + proc.stderr)[-12000:],
    }


def build_manifest(run_tests: bool = True) -> dict:
    checks = [check_project_files(), check_database()]
    if run_tests:
        checks.append(run_unit_tests())
    checks.extend([
        {"name": "live_mininet_baseline", "status": "NOT_RUN", "reason": "Must be executed with Ryu and Mininet running."},
        {"name": "live_link_failure_and_restore", "status": "NOT_RUN", "reason": "Requires a timestamped live experiment."},
        {"name": "live_congestion", "status": "NOT_RUN", "reason": "Requires controlled traffic generation and measured telemetry."},
        {"name": "recovery_failure_and_rollback", "status": "NOT_RUN", "reason": "Requires a controlled failure-injection trial."},
        {"name": "independent_phase12_learning_feedback", "status": "PENDING", "reason": "Trainer has no approved verification sources until evidence is reviewed."},
    ])
    return {
        "project": "Self-Healing Predictive Network Using Digital Twin and Causal AI",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation_policy": "Never mark a live test PASS unless a recorded experiment provides evidence.",
        "checks": checks,
        "software_checks_passed": sum(item["status"] == "PASS" for item in checks),
        "software_checks_failed": sum(item["status"] == "FAIL" for item in checks),
        "live_test_status": "NOT_RUN",
    }


def write_manifest(manifest: dict) -> tuple[Path, Path]:
    REPORTS.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS / "phase16_validation_manifest.json"
    md_path = REPORTS / "phase16_validation_report.md"
    json_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    lines = [
        "# Phase 16 — Final Test Cases and Results Validation", "",
        f"- Generated (UTC): {manifest['generated_at_utc']}",
        f"- Software checks passed: {manifest['software_checks_passed']}",
        f"- Software checks failed: {manifest['software_checks_failed']}",
        f"- Live end-to-end tests: {manifest['live_test_status']}", "",
        "| Check | Status | Notes |", "|---|---|---|",
    ]
    for check in manifest["checks"]:
        note = check.get("reason", check.get("error", ""))
        if check.get("missing"): note = "Missing: " + ", ".join(check["missing"])
        if check.get("name") == "unit_tests": note = f"exit code {check.get('return_code')}"
        lines.append(f"| {check['name']} | **{check['status']}** | {note} |")
    lines += [
        "", "## Required live demonstration", "",
        "1. Start Ryu with topology discovery enabled.",
        "2. Start the redundant Mininet topology and record baseline ping loss/latency.",
        "3. Capture telemetry, then induce congestion using a controlled traffic tool.",
        "4. Disable the primary link, record event timestamps, packet loss and recovery.",
        "5. Verify link restoration and connectivity.",
        "6. Run a deliberately unsuccessful first recovery in a controlled test, then verify safe fallback/rollback.",
        "7. Save raw outputs and populate the Phase 14 trial CSV before reporting quantitative results.",
        "", "Unit-test success does not imply that these live cases have passed.", "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main():
    manifest = build_manifest()
    paths = write_manifest(manifest)
    print(json.dumps({k: manifest[k] for k in ("software_checks_passed", "software_checks_failed", "live_test_status")}, indent=2))
    for path in paths: print(f"Wrote: {path}")
    for item in manifest["checks"]:
        print(f"{item['status']}: {item['name']}")
    return 1 if manifest["software_checks_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
