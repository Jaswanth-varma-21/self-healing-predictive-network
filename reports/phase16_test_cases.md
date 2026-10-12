# Phase 16 — Final End-to-End Test Cases

| ID | Test case | Evidence required | Initial status |
|---|---|---|---|
| TC-01 | Baseline host reachability | `pingall` output, topology/controller logs | Previously recorded in Phase 11; rerun for final release |
| TC-02 | Primary-link failure | link state + `pingall` + timestamps | Previously recorded in Phase 11; rerun for final release |
| TC-03 | Link restoration | interface LIVE + connectivity | Previously recorded in Phase 11; rerun for final release |
| TC-04 | Congestion detection | controlled traffic, telemetry, detector output | NOT RUN in this package build |
| TC-05 | Prediction metrics | independently labelled repeated trials | PENDING trial data |
| TC-06 | Root-cause accuracy | independently verified root cause | PENDING trial data |
| TC-07 | Unsafe telemetry rejection | unit test / rejected input audit entry | Automated test |
| TC-08 | Unsafe route rejection | unit test / audit entry | Automated test |
| TC-09 | Recovery failure and rollback | injected failed action, second strategy, post-check | Twin simulation available; live controller test pending |
| TC-10 | Continuous-learning readiness | approved independent feedback, >=5 examples per class | GATED / pending evidence |
| TC-11 | Live dashboard | browser view + API/SQLite/OVS status | Start dashboard and verify in demo |
| TC-12 | Large-scale experiment | recorded graph simulation and/or live-emulation evidence, clearly separated | Algorithmic simulation harness available |

Run `python3 -m validation.final_validation` to regenerate the software validation manifest. It intentionally keeps live-only cases as `NOT_RUN` unless evidence is supplied.
