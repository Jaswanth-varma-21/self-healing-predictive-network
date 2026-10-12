"""Phase 13 security primitives: input validation, authorization and audit trails.

These controls are intentionally small and auditable. They are not a substitute
for TLS, OS-level isolation, or production-grade identity management.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT_LOG_PATH = Path(os.environ.get(
    "CN_SECURITY_AUDIT_LOG", PROJECT_ROOT / "logs" / "security_audit.jsonl"
))
_AUDIT_LOCK = threading.Lock()

ROLE_PERMISSIONS = {
    "observer": frozenset({"read_status", "read_metrics"}),
    "operator": frozenset({"read_status", "read_metrics", "simulate"}),
    "controller": frozenset({
        "read_status", "read_metrics", "simulate", "reroute", "rollback"
    }),
    "admin": frozenset({
        "read_status", "read_metrics", "simulate", "reroute", "rollback",
        "configure"
    }),
}
ACTION_PERMISSIONS = {
    "NO_ACTION": "read_status",
    "NONE": "read_status",
    "INCREASE_MONITORING": "read_metrics",
    "REROUTE_TRAFFIC": "reroute",
    "ROLLBACK": "rollback",
    "RESTORE_PRIMARY_LINK": "configure",
}
ALLOWED_RECOVERY_ACTIONS = frozenset(ACTION_PERMISSIONS)


def audit_event(event: str, outcome: str = "info", **details: Any) -> dict:
    """Append one JSONL audit event. Secrets must never be passed in details."""
    if not isinstance(event, str) or not event.strip():
        raise ValueError("event must be a non-empty string")
    record = {
        "timestamp": time.time(),
        "event": event.strip(),
        "outcome": str(outcome),
        "details": details,
    }
    payload = json.dumps(record, allow_nan=False, default=str, sort_keys=True)
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _AUDIT_LOCK:
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as stream:
            stream.write(payload + "\n")
    return record


def _walk_values(value: Any, prefix: str = "metrics"):
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk_values(child, f"{prefix}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _walk_values(child, f"{prefix}[{index}]")
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{prefix} contains a non-finite number")
    elif isinstance(value, int) and not isinstance(value, bool):
        return


def validate_telemetry_metrics(
    metrics: Mapping[str, Any],
    *,
    timestamp: float | None = None,
    now: float | None = None,
    max_age_seconds: float | None = None,
) -> tuple[bool, str]:
    """Validate telemetry shape, finite values, known metric bounds and freshness."""
    if not isinstance(metrics, Mapping) or not metrics:
        return False, "metrics must be a non-empty mapping"
    try:
        list(_walk_values(metrics))
    except ValueError as exc:
        return False, str(exc)

    for key, value in metrics.items():
        if not isinstance(key, str) or not key.strip():
            return False, "metric keys must be non-empty strings"
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        number = float(value)
        lower_key = key.lower()
        if "packet_loss" in lower_key or lower_key.endswith("_loss_percent"):
            if not 0.0 <= number <= 100.0:
                return False, f"{key} must be between 0 and 100"
        if any(token in lower_key for token in ("rtt", "latency", "delay")):
            if number < 0:
                return False, f"{key} cannot be negative"
        if any(token in lower_key for token in ("packets", "bytes", "errors", "drops")):
            if number < 0:
                return False, f"{key} cannot be negative"

    if timestamp is not None:
        try:
            ts = float(timestamp)
        except (TypeError, ValueError):
            return False, "timestamp must be numeric"
        if not math.isfinite(ts):
            return False, "timestamp must be finite"
        current = time.time() if now is None else float(now)
        if ts > current + 5.0:
            return False, "timestamp is unexpectedly in the future"
        if max_age_seconds is not None and current - ts > max_age_seconds:
            return False, "telemetry is stale"
    return True, "accepted"


def validate_path(
    path: Iterable[Any],
    adjacency: Mapping[Any, Mapping[Any, Any]],
    failed_links: Iterable[tuple[Any, Any]] = (),
) -> tuple[bool, str]:
    """Reject empty, looping, disconnected or failed-link routes."""
    if isinstance(path, (str, bytes)):
        return False, "path must be a sequence of nodes"
    nodes = list(path)
    if not nodes:
        return False, "path is empty"
    if len(nodes) != len(set(nodes)):
        return False, "path contains a loop"
    blocked = {frozenset(edge) for edge in failed_links}
    for left, right in zip(nodes, nodes[1:]):
        if frozenset((left, right)) in blocked:
            return False, f"path uses failed link {left}-{right}"
        if right not in adjacency.get(left, {}):
            return False, f"path uses undiscovered link {left}-{right}"
    return True, "accepted"


def authenticate_module(presented_token: str | None, expected_token: str | None) -> bool:
    """Constant-time shared-token check for local module/API boundaries."""
    if not isinstance(presented_token, str) or not presented_token:
        return False
    if not isinstance(expected_token, str) or not expected_token:
        return False
    return hmac.compare_digest(
        hashlib.sha256(presented_token.encode()).digest(),
        hashlib.sha256(expected_token.encode()).digest(),
    )


def authorize_action(role: str, permission: str) -> tuple[bool, str]:
    permissions = ROLE_PERMISSIONS.get(role)
    if permissions is None:
        return False, "unknown role"
    if permission not in permissions:
        return False, f"role {role!r} is not allowed to {permission!r}"
    return True, "authorized"


def validate_recovery_recommendation(
    recommendation: Mapping[str, Any],
    *,
    role: str = "controller",
    topology: Mapping[Any, Mapping[Any, Any]] | None = None,
    failed_links: Iterable[tuple[Any, Any]] = (),
) -> tuple[bool, str]:
    """Gate recovery recommendations before an action is considered executable."""
    if not isinstance(recommendation, Mapping):
        return False, "recommendation must be a mapping"
    action = recommendation.get("recovery_action", recommendation.get("action"))
    if not isinstance(action, str) or action not in ALLOWED_RECOVERY_ACTIONS:
        return False, "unknown or missing recovery action"
    allowed, reason = authorize_action(role, ACTION_PERMISSIONS[action])
    if not allowed:
        return False, reason
    if action == "REROUTE_TRAFFIC":
        if recommendation.get("counterfactual_feasible") is not True:
            return False, "reroute requires an explicit feasible counterfactual"
        path = recommendation.get("path")
        if topology is not None:
            if not isinstance(path, (list, tuple)):
                return False, "reroute requires a validated path"
            ok, path_reason = validate_path(path, topology, failed_links)
            if not ok:
                return False, path_reason
    return True, "approved"


def safe_recovery_gate(
    recommendation: Mapping[str, Any],
    *,
    role: str = "controller",
    topology: Mapping[Any, Mapping[Any, Any]] | None = None,
    failed_links: Iterable[tuple[Any, Any]] = (),
    context: Mapping[str, Any] | None = None,
) -> tuple[bool, str]:
    ok, reason = validate_recovery_recommendation(
        recommendation, role=role, topology=topology, failed_links=failed_links
    )
    audit_event(
        "recovery_gate",
        "approved" if ok else "rejected",
        reason=reason,
        action=recommendation.get("recovery_action", recommendation.get("action"))
        if isinstance(recommendation, Mapping) else None,
        context=dict(context or {}),
    )
    return ok, reason
