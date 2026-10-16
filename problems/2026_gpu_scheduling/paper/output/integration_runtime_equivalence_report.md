# Baseline V1 merged-runtime DES equivalence acceptance

- Integrated commit: `1b46c8f65579afea25990cd1254302b520e38a70`
- Runtime: integrated `q3.py` + shared `simulate_pool`; 14 frozen policy/scenario runs, sequential, 900 s / 4096 MiB guards.
- Raw IDs: 224112; job hash `ef14d696adc1b5c7847db49b41a068a998c8cd669e63922c92b3f1c3f32eedb0`; node hash `1aba161961a5a4a1a61aa581383c5e5abe3400b59f8597ba8c4eef7597bc9d18`.

## Gate separation

- Historical ledger validity: **PASS** for the prior persisted-ledger replay; it remains historical evidence and is not a merged runtime execution.
- Merged runtime reproduction: **PASS**.
- Per-ID schedule and physical placement equivalence: **PASS**.
- Numeric metrics and paired waiting/JCT/completion indicators: **PASS / PASS**.
- Per-node physical capacity and raw-routing replay: **PASS**.
- TECHNICAL_BASELINE_READY: **PASS**.

## Frozen 14 runs

| Scenario | FCFS | SJF-HOL |
|---|---:|---:|
| M0 | PASS | PASS |
| S0 | PASS | PASS |
| S1 | PASS | PASS |
| S2 | PASS | PASS |
| S3 | PASS | PASS |
| S4 | PASS | PASS |
| S5 | PASS | PASS |

- Total wall time: 1210.863 s (0.336 h); maximum observed RSS: 383.3 MiB.
- No historical results, manifests, Paper E, Q1/Q2/Q3 activity worktree, scheduler, parameter, or scenario was changed.

## Not executed

- New Q2 G1/G2/G3 simulator reruns and any scheduler/search work were not part of this acceptance.
- Large runtime CSV outputs remain in the ignored local output root for audit; only this summary and report are committed.
