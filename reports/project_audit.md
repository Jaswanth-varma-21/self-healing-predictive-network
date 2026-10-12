# Project Audit — Uploaded Archive Review

## Scope
Reviewed the uploaded `cn_project.rar` source tree, existing Phase 10/11 reports, controller, dashboard, telemetry pipeline, prediction data preparation, storage modules, and tests. This is a source-level audit, not a security penetration test or a fresh live-network test.

## Changes made
- Added a README and explicit 16-phase map.
- Replaced machine-specific absolute project paths with paths derived from each source file, including optional `CN_TELEMETRY_DB` override.
- Added Phase 13 trust helpers, telemetry ingress validation, route validation in the Ryu controller, and JSONL audit logging.
- Added Phase 12 evidence-referenced outcome integration while retaining the trainer's independent source allowlist.
- Added Phase 14 evaluation calculations and a measured-trial CSV template.
- Added Phase 15 reproducible graph-scale simulation.
- Added Phase 16 validation manifest and end-to-end test matrix.
- Added a loopback-only live dashboard combining SQLite telemetry and actual interface probes with clearly labelled twin-only scenario controls.
- Added tests for the new trust, evaluation, experiment, and feedback integration components.

## Existing concerns to preserve in documentation
- `failure_prediction/data/failure_dataset.py` derives `next_failure` from subsequent ping loss/RTT thresholds. These are telemetry-derived proxy labels, not independent ground truth, and must not be reused as Phase 12 independently verified feedback.
- The Phase 11 report documents connectivity under a tested primary-link failure but notes that exact recovery time was not independently measured.
- Phase 14 claims require repeated, matched baseline/proposed trials and independent labels.
- Phase 15's graph simulation must not be presented as large-scale Mininet performance.
- Phase 13 includes core input/path gates and audit controls, but production identity management, OpenFlow TLS, tamper-proof audit storage, and a tested live rollback sequence are not complete.
- Phase 12 learning remains gated while no verification source is approved and sufficient independent outcomes are absent.

## Backup hygiene
Historical `.bak`, phase backup, and pre-integration snapshots are preserved under `archive/legacy_backups/`. Python bytecode caches are removed from the distributable copy.


## Verification performed for this prepared copy
- 31 automated unit tests passed.
- `compileall` completed successfully.
- Dashboard smoke test returned HTTP 200 for `/`, `/health`, `/api/status`, and a simulation scenario POST; the status API read 70 stored telemetry observations from the bundled DB.
- Phase 15 harness ran 50 graph-simulation trials (10 trials at each of 5, 10, 20, 50, and 100 nodes); all tested cases retained graph reachability after the chosen edge failure. This is not live Mininet evidence.
- Phase 16 manifest reports three software checks passed, zero failed; live Mininet congestion and recovery-failure/rollback cases remain `NOT_RUN`.
- Phase 12 trainer currently reports 0 eligible approved feedback samples and leaves the live model unchanged.
- Seventeen hard-coded project-root references in Python source were replaced with project-relative paths or the `CN_TELEMETRY_DB` override.
- Sixteen legacy backup snapshots were retained under `archive/legacy_backups/`; bytecode caches were excluded.
- The identified synthetic test-only learning-feedback row was removed from the distributable SQLite database; original telemetry rows were preserved.

## Final cleanup for Debian live demo (2026-10-11)
- Fixed missing `safe_recovery_gate` import in `failure_prediction/decision/recovery_orchestrator.py` (previously raised `NameError`); the module now also locates the digital-twin packages itself.
- Dashboard (`demo/live_demo.py`) now discovers the real switch-port-to-link mapping from veth peer indexes at runtime, with the static list as fallback. Verified on simulated interface data only; live Mininet confirmation is part of the demo pre-check.
- `telemetry/ovs_telemetry.py` no longer hard-requires `sudo` or `/usr/bin/ovs-ofctl` (works in a Debian root shell, reports a missing binary instead of crashing).
- Removed: `archive/legacy_backups/` (16 backup snapshots), `waste/`, `sdn_controller/live_dashboard.py` (superseded duplicate on the same port), `telemetry/ovs_telemetry_v1_raw.py` (unused), Python bytecode caches, generated audit log.
- Added: `LIVE_DEMO_README.md`, `docs/DEMO_CHEATSHEET.txt`, `scripts/` (Debian setup, environment check, launchers), `tests/test_dashboard_port_discovery.py`. Test suite: 37 tests passing.
- Telemetry database content was not modified. It still contains rows with test sources (`unified_test`, `phase9_counterfactual_test`) in the prediction/causal/recovery tables; they are earlier test outputs, not live results.
- Not verified in the audit environment: live Mininet/Ryu/OVS runs. Phase 16 live cases remain `NOT_RUN` until executed and recorded.
