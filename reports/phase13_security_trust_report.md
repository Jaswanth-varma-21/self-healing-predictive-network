# Phase 13 — Security & Trust Layer

## Implemented
- Telemetry-ingress validation rejects malformed mappings, non-finite values, invalid packet-loss percentages, negative latency/counter values, and optionally stale/future timestamps.
- The Ryu controller validates a computed forwarding path against discovered adjacency and records approved/rejected route decisions.
- Recovery recommendation gate uses an explicit action allowlist, role permissions, and requires `counterfactual_feasible is True` before a reroute can be approved.
- Constant-time shared-token comparison helper is available for local module boundaries.
- Security decisions are appended as JSON Lines to `logs/security_audit.jsonl`.
- Dashboard binds to loopback by default, limits scenario requests, rejects cross-origin POSTs, and its scenario controls never execute system commands.

## Tests
See `tests/test_phase13_trust_layer.py` and `tests/test_phase13_telemetry_guard.py`.

## Limitations
- The token helper is not a full identity provider and does not itself enable TLS for OpenFlow.
- Controller transport authentication, credential rotation, operating-system permissions, and network segmentation require deployment-level configuration.
- The controller's path gate validates forwarding paths; recovery rollback is not yet a fully instrumented live controller workflow.
- Audit logs are append-only by application convention, not tamper-proof storage.

## Phase 13 status
Core trust primitives and input/path gates are implemented. Production-grade authentication and a live rollback test remain future hardening items.
