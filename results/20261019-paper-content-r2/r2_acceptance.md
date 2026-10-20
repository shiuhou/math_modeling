# Paper Content R2 acceptance table

Candidate PDF: `problems/2026_gpu_scheduling/paper/output/problem_b_paper_content_r2.pdf` (7 pages, A4, 11 pt; SHA256 recorded in `r2_build_provenance.json`).

| Sub-item | Status | PDF page | Table/equation or text evidence | Data source and case ID |
|---|---|---:|---|---|
| A1: Q1/Q2 table ownership and GS1 source | 完成 | 3 | Table 2 is the six-pool result; caption says formal C0, ratio only for GPU-series-1 and FF-id elsewhere | `outputs/v2-integration-runtime-20261019/C0/run_metadata.json`, C0; A10 timing checked against B2 |
| A2: Q1 raw work-type statistics | 完成 | 1 | Table 1 reports duration bands, GPU-work shares, and worker strata for all jobs and A10 | `data/raw/job_info_clean.csv`, 224,112 rows |
| A3: Q3 uses corresponding C0--C4 | 完成 | 5--6 | Table 5 labels No substitution, Hash-10%, and Shape-filtered and reports C0--C4 values | Integrated C0--C4 ledgers; mapping in `r2_mapping.md` |
| B1: FCFS/SPT-HOL/SPT-FILL comparison | 完成 | 4 | Table 3 reports mean, P99, maximum, and fixed GPU-work weighted mean with B1, C0, full-A1 IDs | B1 integrated ledger; C0 ledger; full-A1 formal A10 schedule |
| B2: core mean/tail/weighted trade-off | 完成 | 4 | Text states HOL lowers mean and P99 but has a higher maximum; weighted ranking reverses | Same Table 3 sources |
| B3: SPT-HEAD-TIME definition | 完成 | 5 | Section 2.4 defines reservation, feasible backfill, K=200, and timer event behavior from code | `simulator.py` lines 202--251, 428--432, 477--520, 540--577, 600--604; full-C1 |
| C1: gang condition and finite-K qualification | 完成 | 3 | Equation (3) gives `f^- + Δf ≥ k`; text states when `Δf ≥ k` is valid and why finite K can invalidate it | Q2 implementation and formal schedules; source mapping |
| C2: formal worker strata | 完成 | 4--5 | Table 4 has W=1, W=2--8, W≥9, all requested columns, paired counts, and unstable-P99 marks | Full-H1 HOL and full-A1 FILL schedules |
| D1: reader-facing names and supplement mapping | 完成 | 5--6 | Main text uses No substitution, Hash-10%, Shape-filtered; formal C0--C4 mapping is in supplement | `r2_mapping.md`; C0--C4 |
| D2: internal delivery wording removed from正文 | 完成 | 1--7 | PDF text check found no commit, BOM, ZIP, version-history, branch/path or Candidate B wording | Final PDF text scan |
| E1: common A100 denominator | 完成 | 6 | Text uses 3,456-GPU denominator and separates native 2,976 and foreign 480 contributions | C1--C4 saved ledgers; R2 metrics |
| E2: foreign idle fractions and 534/8 qualification | 完成 | 6 | Text reports 44.923%/55.077% at sigma=1, 62.841%/37.159% at sigma=2, and treats 534/8=66.75 as aggregate only | C3/C4 ledgers; physical node-level validation |
| F1: summary structure and conditional policy claim | 完成 | 1 | Summary starts with findings, then method, then the measured sigma=1 management choice | Final PDF abstract |
| F2: strengths and limitations | 完成 | 7 | Dedicated paragraph lists exact accounting strengths and finite-trace/compatibility limits | Final PDF, Section 4 |
| F3: complete AI disclosure | 完成 | 7 | AI statement names ChatGPT, OpenAI Codex, and Claude uses and assigns formal recomputation/checking to the team | Final PDF, Use of AI Tools |
| G1: no new scheduler run | 完成 | 1 | Validation paragraph states no scheduler or replay rerun; all new values are post-processing | `r2_metrics.json`, `README.md` |
| G2: reproducible source mapping and evidence | 完成 | 1--7 | Source paths, hashes, case IDs, and input identity comparison are in the R2 supplement | `r2_mapping.md`, `r2_metrics.json` |
| Format: page count and paper size | 完成 | 1--7 | 7 pages, A4 | `pdfinfo` on final PDF |
| Format: font size | 完成 | 1--7 | 11 pt document class; no table-only shrinking was used | `r2_preamble.tex`, final PDF |
| Format: table/figure consistency | 完成 | 1--6 | Tables 1--5 and Figures 1--3 are present; captions match visible columns and cited values | Final PDF visual review and text extraction |
| Human identity/final wording confirmation | 未完成 | — | Team identity and final human sign-off remain outside the repository evidence | Deliberately left for the team; no names inferred |

The last row is a human handoff item, not an unverified paper claim. R1, V1, the historical V2 candidate PDF, and all prior evidence remain preserved.
