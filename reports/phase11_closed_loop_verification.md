# Phase 11: Closed-Loop Verification

## Project
Digital Twin-Based Autonomous Network Failure Prediction and
Self-Healing Framework Using Causal Artificial Intelligence

## 1. Objective
Verify host connectivity during a primary-link failure, inspect
controller path recomputation, and examine alternate-link counters.

## 2. Test Topology
- Hosts: h1, h2
- Switches: s1, s2, s3
- Primary path: h1 - s1 - s2 - h2
- Alternate path: h1 - s1 - s3 - s2 - h2
- Controller: Ryu using OpenFlow 1.3
- Failure condition: link s1-s2 down

## 3. Test Results

### Test A: Baseline Connectivity
Command: pingall
Result: 0% packet loss (2/2 received)
Status: PASS

### Test B: Connectivity During Link Failure
Command: link s1 s2 down
Command: h1 ping -c 5 h2
Result: 5 packets transmitted, 5 received
Packet loss: 0%
Average RTT: 16.082 ms in the first test
Status: PASS - connectivity maintained during failure

### Test C: Repeat Ping During Link Failure
Command: h1 ping -c 5 h2
Result: 5 packets transmitted, 5 received
Packet loss: 0%
Average RTT: 34.336 ms
Status: PASS

### Test D: Controller Path Recalculation
Ryu logs reported the link-down event and alternate paths:
[1, 3, 2] and [2, 3, 1].
These paths are consistent with forwarding through s3.
Status: PASS - alternate paths reported by the controller

### Test E: Alternate-Link Port Counters
Between the counter snapshots surrounding the second ping:

- s3-eth1 RX packets increased by 23.
- s3-eth1 TX packets increased by 23.
- s3-eth2 RX packets increased by 23.
- s3-eth2 TX packets increased by 23.
- No port drops or errors were reported in the snapshots.

These are cumulative port counters and may include traffic other
than the test ping. They support activity on the alternate links
but do not independently prove the exact path of each ping packet.

Status: SUPPORTING EVIDENCE

## 4. Conclusion
Host-to-host connectivity was maintained during the tested
primary-link failure, with 0% packet loss in both five-packet
ping tests. Ryu reported alternate paths through s3, and both
s3 inter-switch port counters increased during the second test.

The results support successful connectivity under the tested
failure condition. Recovery time has not been measured, and
complete flow-table cleanup and exact packet traversal have not
been conclusively verified.

## 5. Remaining Work
1. Inspect and correct stale or inappropriate forwarding rules.
2. Verify forwarding counters on s1, s2, and s3.
3. Repeat link failure and restoration tests with timestamps.
4. Measure recovery time across repeated trials.
5. Validate restoration and document final results.

### 7. Final Closed-Loop Verification — 2026-10-10

- Ryu rediscovered the complete topology: 3 switches and 6 directed links.
- Baseline connectivity passed: `pingall` reported 0% packet loss (2/2 received).
- The primary link between s1 and s2 was disabled and verified down at s1-eth2.
- The alternate route through s3 was verified using forwarding rules and nonzero packet counters on s1, s3, and s2.
- Connectivity remained available during the primary-link failure: `pingall` reported 0% packet loss (2/2 received).
- The primary link was restored and s1-eth2 was verified LIVE.
- Primary-path forwarding rules appeared again on s1 and s2.
- Final post-restoration connectivity passed: `pingall` reported 0% packet loss (2/2 received).

### Final Phase 11 Assessment

The Mininet experiment provides evidence of alternate-path forwarding during primary-link failure and successful connectivity after restoration.

Limitations:
- Exact failover recovery time was not independently measured.
- The topology is small and emulated; results do not establish large-scale performance.
- The experiment does not by itself validate the prediction engine, causal root-cause analysis, or continuous-learning components.
