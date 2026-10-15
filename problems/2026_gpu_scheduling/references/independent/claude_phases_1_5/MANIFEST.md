# 2026 MCM Problem B — Independent research package (Phases 1–5)

Built only from the official PDF, the two official CSVs, my own scripts, and public mathematics. No other team's material.
Two early ad-hoc scripts that read a file on the user's machine (`verify_mice.py`, `verify_lane_hol.py`) are **excluded**.
Phase 5 corrections are in `ERRATA.md`; where this manifest and an older output disagree, the errata win.

## Data (not bundled — supply the official files)
| file | sha256 |
|---|---|
| job_info_clean.csv | 735bc06c3986b1d0c5932236f8685b7204463829118fc6a1d37030e253ed38e1 |
| node_info_df.csv | 1aba161961a5a4a1a61aa581383c5e5abe3400b59f8597ba8c4eef7597bc9d18 |
| 2026_MCM_GPU_Scheduling.pdf | fb153a547ed57a3d16ab0929c27cccc5d49fc4e568d9c65a273546057e692967 |

## Environment and dependency chain
Python 3.13.16, numpy 2.5.3, pandas 3.0.5, sortedcontainers. Every script reads data only through the environment variables
`MCM_JOB_CSV` and `MCM_NODE_CSV`. Other inputs are package scripts (`sim_node.py`, `p2_sim.py`, `audit_v3.py`, `p2_gs1.py`, imported or exec'd)
and `p2_st_*.npy`, which `p2_run.py` generates inside `scripts/`. Nothing outside the package is read. Prototype run times
are for this pure-Python single-core prototype only.

## Run
```
MCM_JOB_CSV=/path/job_info_clean.csv MCM_NODE_CSV=/path/node_info_df.csv bash run_core_checks.sh
```
One text file per check is written to `results/core_run/`. Reference outputs: `results/core_run/` (full rerun after the errata),
`results/erratum_run/` (Phase 5 checks, first run), `results/phase1_logs/` (historical, superseded where noted).

## Definitions
δ_j = C_j − r_j − p_j (delay; equals the wait W_j without preemption). Z(t) = {j : r_j ≤ t < r_j+p_j}. G_j = gpu_request·worker_num; a_j = G_j p_j.
q(t) = minimum number of jobs to delete from Z(t) so that the remaining GPU sum ≤ C.
SPT-strict: order by (p, r, job_name); stop all new starts while the head does not fit. SPT-skip: same order, skip non-fitting jobs (scan cap 500).
**Initial submission batch** = jobs with submit_time = 0 (no claim about their pre-trace history).
A10 is simulated as 2,494 identical 1-GPU machines. All simulations drain to completion; all results are in-sample on one trace.

## Mathematical results (status after errata)
| id | statement | scope / premises | evidence |
|---|---|---|---|
| T1 | Σ a_j W_j = ∫(D0−D)dt ≥ ∫_0^∞ B(t)dt, B = Lindley(O0 − C); the integral includes the tail B(t*)²/(2C) | single pool, non-preemptive, fixed durations | e1_area_tail.py: A10 560.5213678903029 h |
| T2 | Σ_j w_j ℓ_j ≥ ∫K_w; ℓ_j ≤ min(δ_j,p_j) (preemptive gang) and ℓ_j = min(W_j,p_j) (non-preemptive) ⇒ Σ w_j min(δ_j,p_j) ≥ ∫K_w ⇒ Σ δ_j ≥ ∫q | single pool, all workers of a job in or out of service together, fixed durations, any placement | p2_countlb_all.py + audit_v1.py: 22.3179 h; 0 pointwise violations |
| T3 | exact accounting Σ W = ∫q + [Σ min(W,p) − ∫q] + Σ(W−p)^+ ; middle term = ∫(#Z not in service − q) | non-preemptive; no causal attribution of the middle term | p4_checks.py truncated |
| T3' | shape bound max(q_G, q_C, q_GH, q_CH) valid with SEPARATE GPU-heavy / CPU-heavy counts | — | e2_shape_exact.py: zero extra in every pool |
| P1 | gang starvation: identical unit machines, strict non-idling (no scan cap), unit backlog persists after every epoch, fewer than k releases per epoch | finite trace ⇒ long waits until the backlog clears, not "indefinite" | p2_run.py skip: 570/570 |
| P2 | FCFS-strict head of width k starts at the (k−f)-th earliest release; idle ≤ k·h | no overtaking | — |
| T4 | FCFS-strict start times are monotone in a non-revoking capacity function that changes only at epochs | identical unit machines, same arrival-consistent order | — |
| T5 | decoupling: trunk rule + R ≥ max short-job width, kept until drain, FCFS short jobs ⇒ each short job starts no later than in an isolated R-machine system | fails for SPT (counterexamples in ERRATA/Phase 3) | p2_run.py decouple: 0/87,953 |
| T6 | initial-batch re-homing, unit width, common start 0, capacity H(t) or uniform 8L: greedy longest-first is optimal for (ii) moved work, (iii) unnormalised LBs, (iv) LBs normalised by the FIXED original population/area | not proved for actual total delay; not for remaining-population normalisation; not for k>1 or job-specific σ | p2_rehome.py, e1_area_tail.py, e4_sigma_fixed.py |
| T7 | net change of total delay over the fixed population (native weights) is −ΔB + (σ−1)Σ p_moved; benefit ⇔ σ < 1 + ΔB/Σp_moved (count); area analogue with Σ a_j p_j | prerequisites below | e4_sigma_fixed.py |
| W1 | **withdrawn**: "no downward placement ⇒ zero wait ⇔ O0 ≤ C" (ERRATA E4) | — | e3_toy_counterexamples.py |

T7 prerequisites: (1) the population and weights are fixed: all 111,284 A10 jobs, weight 1 or the native a_j = k_j p_j;
(2) the A10 policy is the same before and after (SPT-strict); (3) moved jobs start on the host at their submission time 0
(480 ≤ 8·60 slots, all workers single, cpu ≤ 16 so 8 per 128-vCPU node); (4) the moved jobs' native delay is 0 (verified);
(5) host jobs are unaffected over the whole occupancy horizon (dedicated nodes: A100's own jobs run on 372 nodes, verified 100 %
zero-wait under FCFS and SJF best-fit; this does not depend on σ because lent nodes are never shared);
(6) one common σ for all moved jobs, measured against native p_j. ΔB is policy-dependent and in-sample.

## Key outputs (full precision in results/)
- A10 count LB 22.3179 h (two methods). A10 area LB 560.5213678903029 h (front 560.3121107156877 + tail).
- SPT-strict A10: mean 32.906454035021504 h (fixed n = 111,284); areaW 677.7 h; truncated part 30.65 h, excess 2.25 h.
- Q3 (L = 60, 480 jobs): fixed-denominator mean delay 32.906454 h → 16.510615 + (σ−1)·11.585148 h;
  σ*_count = 2.415246367625465, σ*_area = 1.806762177008876; count LB of remaining jobs / n = 13.727630025180819 h;
  area LB (fixed denominator) 270.0587983943209 h.
- GS1 ratio-matched: 9,643/9,643 zero wait, integer ledger 0 violations (trace-specific constructive result).

## Scripts
eda1–6.py, mice.py (Phase 1 exploration) · lb3.py (area LB, front only — superseded by e1) · sim_id.py, sim_tr.py (Phase 1; their "sjf" is SPT-skip)
· sim_node.py (node-level simulator) · sim_q3.py, q3fluid.py, sim_lend.py (Phase 1 Q3, superseded) · p2_sim.py, p2_run.py, p2_anal.py
· p2_countlb.py, p2_countlb_all.py, audit_v1.py · p2_gs1.py, p2_gs1_validate.py, audit_v3.py, audit_v4.py, p4_gs1_fallback.py
· p2_rehome.py, p2_sigma.py, p4_lend60.py · p4_checks.py (modes truncated / renewal / gs1cond / a100lend; mode `shape` is WITHDRAWN, see E3)
· e1_area_tail.py, e2_shape_exact.py, e3_toy_counterexamples.py, e4_sigma_fixed.py (Phase 5 errata).
