# B V2 Candidate Integration

Status date: 2026-10-19 (Asia/Shanghai). This task continues the released Baseline V1. It does not rebuild the cleaned branches, change `main`, move the baseline tag, modify V1 outputs, or start a scheduler/search.

## Fixed sources and merge

The candidate worktree is `math_modeling-b-v2-candidate` on `integration/b-v2-candidate`. It starts from `origin/main` `8f2e99ccae31c9559fa726884fda2637d1c0f921`, then merges the fixed Q2, GS1, and Q3 candidate branches with normal merges. The only source-code conflict was the shared simulator signature; it retains `diagnostics`, `placement`, and `node_order`. The only evidence conflict was `results/README.md`, resolved by retaining baseline navigation and adding V2 source pointers. No old scheduler directory was copied wholesale.

Fixed source commits are GS1 `ffdcc7609969094bc1ceaeef650d99b0beae8208`, Q2 `fcd7bafdb002221b42e11ce8ba2dbcfe57fcd0cd`, Q3 `56ea09021d5ad5088ad5ed7242d8fab0c3115667`, and Baseline tag `2026-mcm-b-baseline-v1` at `4ee2c6bfa98cf7177ff976abe73b122889437f46`. Raw inputs are unchanged: node SHA `1aba161961a5a4a1a61aa581383c5e5abe3400b59f8597ba8c4eef7597bc9d18`, job SHA `ef14d696adc1b5c7847db49b41a068a998c8cd669e63922c92b3f1c3f32eedb0`.

## Gates

| Gate | Status | Evidence |
|---|---|---|
| SOURCE_INTEGRATION | PASS | merge commits and source index |
| Q2_PERSISTED_REPLAY | PASS | 14/14 read-only validator cases; `q2_persisted_replay.json` |
| V1_DEFAULT_RUNTIME_RECOVERY | PASS | B1/B2 exact per-ID/resource/placement comparisons |
| V2_SELECTED_RUNTIME_VALIDATION | PASS | C0, C1, C2, C3, C4 exact comparisons plus route/physical/metric checks |
| PAPER_CANDIDATE_VALIDATION | PASS | fresh nine-page A4 PDF, Tectonic 0.17.0, rendered nine-page preview inspected |
| CODE_SUPPLEMENT | PASS | 63,904-byte ZIP, no raw CSV or large account |
| EVIDENCE_DISTRIBUTION | BLOCKED | Q2/Q3 large persisted files are local-only; original cross-machine replay remains unavailable |
| HUMAN_REVIEW | NOT_RUN | team review is required |
| SUBMISSION_READY | BLOCKED | names/institution/advisor and final AI-use record still require team confirmation; official separate guidelines PDF remains unavailable |

## Fresh runtime check

`experiments/run_v2_integration_case.py` ran the seven allowed cases sequentially with the integrated `q3.py` and shared `simulate_pool`, all 224,112 IDs, fixed configuration, shared-timer event mode, 90-day horizon, and explicit 900-second/4-GiB child guards. Cases B1 (FCFS/M0/FF), B2 (SJF-HOL/M0/FF), C0 (M0/GS1 ratio), C1 (R0 sigma 1), C2 (R0 sigma 2), C3 (R-shape sigma 1), and C4 (R-shape sigma 2) are PASS. Every case passed independent route audit, physical capacity replay, metric validation, and exact common-field/placement comparison with its fixed local reference. Runtime wall cost was 520.74 seconds; maximum observed RSS was 512.75 MiB. The first B1 attempt exposed a reference-selection bug in the harness (it compared FCFS against SJF-HOL); that diagnostic is retained under the ignored runtime output `B1_first_diff`, and the corrected run passed. No historical file was changed.

The fourteen Q2 cases (65k A1-A4/H1-H2/C1 and full A1-A4/H1-H2/C1) are PASS as read-only persisted artifact validation. This is separate from fresh merged-runtime execution. The original evidence index still reports the cross-machine persisted replay as unavailable, and all referenced ledgers remain `LOCAL_ONLY`.

## Paper and supplement

`paper/output/pdf/problem_b_v2_candidate.pdf` is a new candidate; the unchanged V1 PDF remains in place. It is 9 pages, A4, SHA256 `6249fc0e305ef33880860b577341ba8814e399663952c9e9818f6ca7c2e11e92`. It is based on the V1 document and adds only a bounded integration section with fixed sources and limitations. The source index is `paper/paper_sources_v2.json`. The code supplement candidate is `paper/output/code_supplement_v2_candidate.zip`, 63,904 bytes, SHA256 `958772c8cbc90af656325022d89149f0ac5b3265cd1ff3c736b32a3a55b2e723`; raw CSV and large ledgers are excluded.

This candidate is ready for team review as a technical baseline candidate. It is not a submission release while distribution, identity, human review, and disclosure gates remain blocked.
