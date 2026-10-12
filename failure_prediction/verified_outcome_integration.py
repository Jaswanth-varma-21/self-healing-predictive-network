"""Evidence-referenced integration point for Phase 12 continuous learning.

Callers are responsible for ensuring that verification_source/evidence_reference
refer to genuinely independent evidence. Recording feedback does not approve its
source for training; learning_trainer maintains a separate allowlist.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from failure_prediction.models.weighted_logistic_predictor import FEATURES
from failure_prediction.continuous_learning import record_verified_outcome


def record_experiment_outcome(
    node: str,
    measured_features: Mapping[str, Any],
    verified_failure: int,
    verification_source: str,
    evidence_reference: str,
    predicted_failure: int | None = None,
    notes: str | None = None,
) -> int:
    if not isinstance(evidence_reference, str) or not evidence_reference.strip():
        raise ValueError("evidence_reference is required")
    if not isinstance(measured_features, Mapping):
        raise ValueError("measured_features must be a mapping")
    missing = [name for name in FEATURES if name not in measured_features]
    if missing:
        raise ValueError(f"missing required features: {missing}")
    clean = {}
    for name in FEATURES:
        value = measured_features[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a finite number")
        if not math.isfinite(float(value)):
            raise ValueError(f"{name} must be a finite number")
        clean[name] = float(value)
    evidence_note = f"evidence_reference={evidence_reference.strip()}"
    combined_notes = f"{notes.strip()} | {evidence_note}" if isinstance(notes, str) and notes.strip() else evidence_note
    return record_verified_outcome(
        node=node,
        features=clean,
        verified_failure=verified_failure,
        verification_source=verification_source,
        predicted_failure=predicted_failure,
        notes=combined_notes,
    )
