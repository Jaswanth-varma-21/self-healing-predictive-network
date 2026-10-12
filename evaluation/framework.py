"""Metrics and report generation for Phase 14.

Only rows with measured values contribute to metric summaries. Missing values
remain unavailable; this module does not invent experimental results.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "reports" / "results"


def _binary(value: Any, field: str) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int) and value in (0, 1):
        return value
    if isinstance(value, str) and value.strip() in {"0", "1"}:
        return int(value.strip())
    raise ValueError(f"{field} must be binary 0 or 1, got {value!r}")


def binary_classification_metrics(
    records: Iterable[Mapping[str, Any]],
    actual_key: str = "actual_failure",
    predicted_key: str = "predicted_failure",
) -> dict[str, Any]:
    rows = list(records)
    tp = tn = fp = fn = 0
    for row in rows:
        actual = _binary(row[actual_key], actual_key)
        predicted = _binary(row[predicted_key], predicted_key)
        if actual and predicted: tp += 1
        elif not actual and not predicted: tn += 1
        elif not actual and predicted: fp += 1
        else: fn += 1
    total = len(rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "samples": total,
        "TP": tp, "TN": tn, "FP": fp, "FN": fn,
        "accuracy": (tp + tn) / total if total else None,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall)
        if precision + recall else 0.0,
    }


def numeric_summary(records: Iterable[Mapping[str, Any]], key: str) -> dict[str, Any]:
    values = []
    for row in records:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            values.append(number)
    return {
        "count": len(values),
        "mean": statistics.fmean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def _summarize_group(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    labelled = [
        row for row in rows
        if row.get("actual_failure") not in (None, "")
        and row.get("predicted_failure") not in (None, "")
    ]
    return {
        "total_trials": len(rows),
        "labelled_trials": len(labelled),
        "classification": binary_classification_metrics(labelled) if labelled else None,
        "prediction_lead_time_seconds": numeric_summary(rows, "prediction_lead_time_seconds"),
        "root_cause_accuracy": numeric_summary(rows, "root_cause_correct"),
        "recovery_time_ms": numeric_summary(rows, "recovery_time_ms"),
        "packet_loss_percent": numeric_summary(rows, "packet_loss_percent"),
        "latency_ms": numeric_summary(rows, "latency_ms"),
        "throughput_mbps": numeric_summary(rows, "throughput_mbps"),
        "availability_percent": numeric_summary(rows, "availability_percent"),
        "false_recovery_rate": numeric_summary(rows, "false_recovery"),
    }


def evaluate_records(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    overall = _summarize_group(rows)
    by_system: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        system = str(row.get("system") or "unspecified").strip().lower()
        by_system.setdefault(system, []).append(row)
    per_system = {name: _summarize_group(group) for name, group in sorted(by_system.items())}

    # Proposed-minus-baseline deltas are computed only when both means exist.
    comparison = {}
    baseline = per_system.get("baseline")
    proposed = per_system.get("proposed")
    metrics = (
        "prediction_lead_time_seconds", "recovery_time_ms", "packet_loss_percent",
        "latency_ms", "throughput_mbps", "availability_percent", "false_recovery_rate",
    )
    for metric in metrics:
        left = baseline[metric]["mean"] if baseline else None
        right = proposed[metric]["mean"] if proposed else None
        comparison[metric] = (
            right - left
            if isinstance(left, (int, float)) and isinstance(right, (int, float))
            else None
        )
    bcls = baseline.get("classification") if baseline else None
    pcls = proposed.get("classification") if proposed else None
    for metric in ("accuracy", "precision", "recall", "f1"):
        left = bcls.get(metric) if bcls else None
        right = pcls.get(metric) if pcls else None
        comparison[metric] = right - left if left is not None and right is not None else None

    overall.update({
        "by_system": per_system,
        "proposed_minus_baseline": comparison,
        "evidence_note": (
            "Metrics are calculated only from supplied trial rows. "
            "Comparison deltas are null unless both baseline and proposed measurements exist."
        ),
    })
    return overall

def read_trials(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_report(result: Mapping[str, Any], output_dir: str | Path = RESULTS_DIR) -> tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "phase14_evaluation.json"
    md_path = out / "phase14_evaluation.md"
    json_path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    lines = [
        "# Phase 14 — Evaluation Results",
        "",
        "> This report reflects only rows provided to the evaluation framework. Missing measurements are not inferred.",
        "",
        f"- Total trials: {result.get('total_trials', 0)}",
        f"- Labelled trials: {result.get('labelled_trials', 0)}",
        "",
        "## Prediction quality",
        "",
    ]
    classification = result.get("classification")
    if classification:
        for key in ("samples", "TP", "TN", "FP", "FN", "accuracy", "precision", "recall", "f1"):
            lines.append(f"- {key}: {classification.get(key)}")
    else:
        lines.append("- Not available: no independently labelled evaluation rows.")
    for key in (
        "prediction_lead_time_seconds", "root_cause_accuracy", "recovery_time_ms",
        "packet_loss_percent", "latency_ms", "throughput_mbps",
        "availability_percent", "false_recovery_rate",
    ):
        item = result.get(key, {})
        lines.append(f"- {key}: {item.get('mean')} mean over {item.get('count', 0)} measured rows")
    lines += ["", "## Baseline vs proposed", ""]
    by_system = result.get("by_system", {})
    if "baseline" in by_system and "proposed" in by_system:
        for system_name in ("baseline", "proposed"):
            summary = by_system[system_name]
            cls = summary.get("classification")
            lines.append(f"### {system_name.title()}")
            lines.append(f"- Trials: {summary.get('total_trials')}")
            if cls:
                lines.append(f"- Accuracy / precision / recall / F1: {cls['accuracy']} / {cls['precision']} / {cls['recall']} / {cls['f1']}")
            else:
                lines.append("- Prediction metrics unavailable: no labelled rows.")
        lines.append("")
        lines.append("Proposed-minus-baseline deltas:")
        for metric, delta in result.get("proposed_minus_baseline", {}).items():
            lines.append(f"- {metric}: {delta}")
    else:
        lines.append("Not available: CSV must contain both `system=baseline` and `system=proposed` trial rows.")
    lines += [
        "",
        "## Interpretation",
        "",
        "Use the same topology, traffic profile, failure scenarios and repetition count for baseline and proposed-system trials.",
        "Do not compare a simulation-only value with a live measurement as if they were equivalent.",
        "Record independent ground truth for failures and root causes. Keep unmeasured metrics as unavailable.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="CSV file of measured evaluation trials")
    parser.add_argument("--output-dir", default=str(RESULTS_DIR))
    args = parser.parse_args(argv)
    result = evaluate_records(read_trials(args.input))
    json_path, md_path = write_report(result, args.output_dir)
    print(json.dumps(result, indent=2))
    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")


if __name__ == "__main__":
    main()
