# Report to formal evidence index

All paths below are relative to the ZIP root. All included CSV/JSON files are small
saved formal evidence or read-only derivatives. No prototype numbers are used.

| Report item | Included source and field / case |
|---|---|
| Q1 / Table 1 | `results/20261019-paper-content-r2/r2_metrics.json`, `q1_type_stats`, all 224,112 jobs and original A10 111,284 jobs; raw CSV identity in `results/20261019-paper-content-r1/input_comparison.json` |
| Figures 1-2 and Q1 statistics | `results/20261014-b-q1-intake-4a8f8f2b/`; audited Q1 functions and publication figure adapter; `figures/q1_daily_demand.csv` records exact daily overlaps. The window is 7,775,878 seconds, not the scheduler's nominal 90 days. |
| Table 2 | `results/20261019-paper-content-r2/r2_metrics.json:q2_c0_six_pool`; C0 integrated physical/cohort metrics in `results/20261019-b-v2-integration-candidate/v2_runtime_equivalence.json`. GS1=ratio, all other pools=FF-id. |
| Table 3 | Same R2 metrics: `q2_a10_three_policy`; FCFS=B1, SPT-HOL=C0, SPT-FILL=full-A1. Fixed raw weights are worker_num × gpu_request × original duration. Full A10 GPU-seconds = 40,028,314,872. |
| Table 4 | Same R2 metrics: `q2_worker_strata`; original full-H1 and full-A1 schedules paired by job ID. Full-H1/HOL and C0/HOL A10 values agree; C0/B2 A10 timing equality is recorded. No full-cluster quantiles are assembled from pool quantiles. |
| Job-count bound and equation (6) | `results/20261019-paper-content-r1/r1_metrics.json:q2_bound_components_hours`; lower-bound derivation and code in the report and `experiments/analyze_m2f_bounds.py`; `results/20261015-b-q2-m2f-01/` retains formal evidence. |
| GPU-work lower bound | `results/20261015-b-q1-capacity-bound/q1_capacity_bounds.json`; unchanged `q1.capacity_bound`; different objective from the count bound. |
| GS1 constructive optimum | `results/20261018-b-gs1-placement-v2-r1/comparison.json`, ratio summaries and strict-replay reports. All 9,643 jobs wait zero; nonnegative waiting gives optimum zero for this fixed instance. |
| SPT-HEAD-TIME and K/timer | `results/20261018-b-q2-v2-r1-01/summaries/q2-v2-full-c1.json`, `exact_comparison.json`, `cost_ratios.json`, `tables.md`. The original case name full-C1 remains here only, distinct from Q3 C1. |
| Table 5(a) | `results/20261019-b-v2-integration-candidate/v2_runtime_equivalence.json`, explicit case keys C0-C4: `metrics.cohorts.original_A10.mean_wait_hours`, `.mean_jct_hours`, `metrics.cohorts.ALL.mean_jct_hours`, `.completed_at_horizon`. All use GS1 ratio; historical ALL results with FF-id are not substitutes. |
| Table 5(b) | `results/20261020-final-publication/saved_timing_checks.json`, exact C0-paired A10 later-finish and native-A100 increased-wait counts; independently matches `results/20261018-b-q3-v2-r1-6f2c8a10/paired.csv` selectors policy=SJF-HOL, reference=M0, option R0/R-shape and sigma 1/2. Historical paired.csv was not rewritten. |
| Main Q3 aliases | C0=No substitution/M0; C1=Hash-10%/R0/sigma1; C2=Hash-10%/R0/sigma2; C3=Shape-filtered/R-shape/sigma1; C4=Shape-filtered/R-shape/sigma2. A historical M1/S0 is R0 sigma1; historical S5 is R0 sigma2. |
| Baseline bridge | `saved_timing_checks.json:C0_B2_cohort_equality` compares every ID and timing/resource field for A10 and native A100. The prior integrated report compares B2 and C0 to the same historical M0 outside GS1. This supports the harm baseline bridge only for those cohorts, not ALL. |
| FCFS Q3 comparisons | `results/20261018-b-q3-v2-r1-6f2c8a10/main_table.csv`, select policy=FCFS, cohort=A10, option=R0/R-shape, sigma=1/2. Comparison and two-point maxima are separate; no interval guarantee. |
| A100 allocation | `saved_timing_checks.json:records[].allocation` sums integer clipped GPU-seconds in saved C1-C4 job timings. Partition-own denominators are 2,976 and 480 GPUs; all-pool denominator is 3,456. The displayed weighted identity is checked against those sums. |
| Figure 3 and negative sensitivity | `results/20261015-b-q3-fixed-split-c9e8f1a2/metrics.json` and `results/20261015-b-q3-s2-fixed-split-v1/sensitivity_metrics.json`. 30/60/90 donors and 10% routing, sigma1; historical GS1 FF-id, but plotted A10/native-A100 cohorts are unaffected. Native S4 harm is compared with S0, whose native timing equals M0 in this instance. |

The machine-readable full-precision Table 5 field mapping and input digests are
`problems/2026_gpu_scheduling/paper/final_publication/generated/numerical_source_map.json`.

## Algorithm wording and executable source

SPT-HOL is the paper name of the unchanged SJF-HOL alias. SPT-FILL uses K=200.
For SPT-HEAD-TIME, the code reserves the first future release with a feasible
node-level witness for a blocked head. TIME backfill requires current feasibility
and finish no later than the immutable promise. K counts candidate attempts after
the blocked-head bypass begins. Shared timer events are extra dispatch epochs, not
urgent promotion for this policy. See `src/gpu_scheduling/simulator.py` within the
problem directory (reservation building, dispatch, and event handling) and the
saved full-C1 summary. The gang condition is f^- + Delta f >= k; simplifying it
requires zero free slots after preceding dispatch and continuous feasible
single-worker backlog. Finite K can invalidate that simplification.

## Distribution and reproducibility limits

Saved large schedules and node ledgers remain **LOCAL_ONLY**, with hashes and
case identifiers preserved in the included metadata. They are neither required
for imports, small smoke, table generation, nor included by symlink. Exact replay
of the historical ledgers on a different machine was not performed for this ZIP.
The raw files must be obtained from authorized competition materials; they are not
redistributed. Portable reproduction creates fresh timings from those inputs.
No new full-trace scheduling or historical replay occurred in this publication task.

Private absolute path prefixes in copied JSON are replaced by
`LOCAL_ONLY/<historical-store>/...`; they are provenance, not executable inputs.
Both the original source byte hash and packaged byte hash are recorded. All core
Python source files are copied without modification. Wrappers only provide paths,
frozen case selection, output writing, and packaging checks. They make no new model
or parameter choice. Human approval of the exact report and ZIP remains separate.
