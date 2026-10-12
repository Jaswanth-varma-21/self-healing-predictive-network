# Phase 14 — Evaluation Framework

The `evaluation/framework.py` module calculates confusion-matrix metrics, accuracy, precision, recall, F1, and numeric summaries for lead time, root-cause correctness, recovery time, packet loss, latency, throughput, availability, and false-recovery counts.

## Required experiment protocol
1. Run baseline reactive routing and proposed predictive self-healing on equivalent conditions.
2. Repeat each scenario and preserve raw logs and timestamps.
3. Populate `data/templates/evaluation_trials_template.csv` with one row per trial and evidence references.
4. Use independent failure and root-cause labels. Do not use a feature itself as the ground-truth label.
5. Run `python3 -m evaluation.framework --input data/my_evaluation_trials.csv`.

## Current result status
The framework is implemented and unit-tested. No baseline-versus-proposed performance claim is made until a measured trial CSV is populated. Missing measurements remain null/empty rather than being inferred.
