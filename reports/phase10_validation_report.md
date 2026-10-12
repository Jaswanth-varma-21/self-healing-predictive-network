# Phase 10: Live Network Self-Healing and Recovery Validation

## Project
Digital Twin-Based Autonomous Network Failure Prediction and
Self-Healing Framework Using Causal Artificial Intelligence

## 1. Objective
Validate host connectivity, simulate a network link failure,
inspect forwarding paths, and test connectivity after restoration.

## 2. Test Topology
- Hosts: h1, h2
- Switches: s1, s2, s3
- Primary path: h1 - s1 - s2 - h2
- Alternate path: h1 - s1 - s3 - s2 - h2
- Controller: Ryu using OpenFlow 1.3

## 3. Test Results

### Test A: Baseline Connectivity
Command: pingall
Result: 0% packet loss (2/2 received)
Status: PASS

### Test B: Direct Link Failure
Command: link s1 s2 down
A subsequent pingall reported 0% packet loss.
Status: PASS - connectivity maintained during the failure

### Test C: Forwarding Path Inspection
Ryu logs reported paths [1, 3, 2] and [2, 3, 1].
These paths are consistent with forwarding through s3.
Flow counters showed activity on the s1 alternate-output rule.
However, s3 forwarding-rule counters remained at zero in
the inspected snapshots. Exact packet traversal and the
failure-triggered recovery sequence need further verification.
Status: PARTIAL

### Test D: Link Restoration
Command: link s1 s2 up
Switch s1 showed the direct-link port as LIVE.
A subsequent pingall reported 0% packet loss (2/2 received).
Status: PASS

## 4. Conclusion
The redundant Mininet topology maintained host connectivity
during the tested direct-link failure and after link restoration.
Ryu logs reported alternate paths through s3.

These results are promising, but they do not by themselves
prove a complete, failure-triggered automatic self-healing
sequence. Further verification of topology-change events,
installed forwarding rules, and packet counters is required.

## 5. Next Work
1. Correlate the link failure with Ryu topology-change logs.
2. Verify forwarding rules and packet counters on s1, s2, and s3.
3. Repeat the failure and recovery test with recorded timestamps.
4. Measure packet loss and recovery time across repeated trials.
