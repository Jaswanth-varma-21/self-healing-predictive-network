# Phase 15 — Large-Scale Experiments

`experiments/large_scale.py` creates deterministic redundant graphs at configurable sizes, removes a primary edge, recomputes a shortest path, and records reachability, route hops, and algorithmic route-computation time.

Run:

```bash
python3 -m experiments.large_scale --sizes 5,10,20,50,100 --repetitions 10
```

Outputs:
- `reports/results/phase15_scale_trials.csv`
- `reports/results/phase15_scale_summary.json`

## Interpretation boundary
These experiments exercise the graph algorithm only. They are not Mininet runs, not throughput benchmarks, and not network recovery-time measurements. To claim large-scale emulated network results, a Mininet or other network-emulation experiment must run at the reported scale and preserve raw evidence.
