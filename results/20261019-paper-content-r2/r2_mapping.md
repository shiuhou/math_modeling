# Paper Content R2 source mapping

All numbers in the R2 PDF are post-processed from the formal artifacts below. No scheduler or replay was run for R2.

| Paper item | Reader-facing label | Formal case / source | Configuration or check |
|---|---|---|---|
| Q1 raw workload statistics | All trace; A10 subset | `problems/2026_gpu_scheduling/data/raw/job_info_clean.csv` | Duration, GPU-work, worker counts computed directly from all 224,112 rows |
| Q2 six-pool table | SPT-HOL, C0 placement | Case `C0`: `outputs/v2-integration-runtime-20261019/C0/run_metadata.json`; ledger `outputs/v2-integration-runtime-20261019/C0/jobs.csv.gz` | GPU-series-1 uses `ratio`; all other pools use `ff-id`; C0 status PASS |
| Q2 FCFS row | FCFS | Case `B1`: `outputs/v2-integration-runtime-20261019/B1/jobs.csv.gz` and `run_metadata.json` | Full 224,112-job integrated schedule, A10 row selected |
| Q2 SPT-HOL row | SPT-HOL | Case `C0` above | C0 A10 timing equals B2 by job ID and start/finish; GS1 placement therefore does not affect the A10 row |
| Q2 SPT-FILL row | SPT-FILL | Case `full-A1`: `/home/shiuhou/mm/math_modeling-b-q2-k-ablation/outputs/q2-v2-full-a1/a10-111284-theta604800-spt-fill/SPT-FILL_job_times.csv.gz` | Formal complete A10 schedule |
| Q2 HOL worker strata | SPT-HOL side | Case `full-H1`: `/home/shiuhou/mm/math_modeling-b-q2-k-ablation/outputs/q2-v2-full-h1/a10-111284-theta604800-spt-hol/SPT-HOL_job_times.csv.gz` | Formal complete A10 schedule; paired with full-A1 by job ID |
| Q2 GS1 baseline | FF-id baseline | Cases `B1` (FCFS) and `B2` (SPT-HOL) | B1/B2 integrated runs use FF-id; C0 is the ratio placement result |
| Q2 SPT-HEAD-TIME | Bounded reservation policy | Code `problems/2026_gpu_scheduling/src/gpu_scheduling/simulator.py`, lines 202--251, 428--432, 477--520, 540--577, 600--604; saved summary `/home/shiuhou/mm/math_modeling-b-q2-k-ablation/outputs/q2-v2-full-c1/a10-111284-theta604800-spt-head-time/summary.json` | `theta=604800 s` (168 h), `K=200`, shared timer; saved schedule and validation PASS |
| Q3 No substitution | No substitution | Case `C0` for the integrated SPT-HOL row | Historical mapping: M0 |
| Q3 Hash-10% | Hash-10% | Cases `C1` and `C2` for sigma 1 and 2 | Historical mapping: R0/S0; 60 of 432 A100 nodes and deterministic 10% selected A10 subset |
| Q3 Shape-filtered | Shape-filtered | Cases `C3` and `C4` for sigma 1 and 2 | Historical mapping: R-shape; 10,604 routed and 605 shape-rejected A10 jobs |
| Q3 historical negative cases and figure | Historical sensitivity | `results/20261015-b-q3-s2-fixed-split-v1/` and `results/20261018-b-q3-v2-r1-6f2c8a10/` | Historical sensitivity is kept separate from C0--C4 integrated results |
| A100 allocation rates | Full-pool denominator | C1--C4 saved ledgers and R2 post-processing | Denominator is 3,456 GPUs; native 2,976 and foreign 480 contributions are reported separately |

## SPT-HEAD-TIME implementation wording

The code creates a reservation when the blocked SPT head has no current node-level plan. It searches future finish events, stores the first release event with a feasible head witness, and then checks backfill candidates using current feasibility plus `now + duration <= promised_R` for the TIME policy. The candidate-attempt budget starts only after a blocked head starts a bypass scan. In shared-timer mode, arrival-plus-theta timer events enter the event loop and trigger dispatch; SPT-HEAD-TIME is not in the urgent set, so timer events do not mark jobs urgent. This is the wording used in the PDF.

## Input identity

Formal-run `job_info_clean.csv`: SHA256 `ef14d696adc1b5c7847db49b41a068a998c8cd669e63922c92b3f1c3f32eedb0`.
Historical-hash `docs/job_info_clean.csv`: SHA256 `735bc06c3986b1d0c5932236f8685b7204463829118fc6a1d37030e253ed38e1`.
They have equal IDs and Decimal-semantic fields but different byte serialization; this fact is kept in the supplement rather than the paper body.
