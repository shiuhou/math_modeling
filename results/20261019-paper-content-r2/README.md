# Paper Content R2

R2 is a read-only paper revision layered on the validated R1 candidate. It performs no scheduler or persisted-replay rerun. New values are generated only from the formal raw job CSV, saved C0/B1/B2 integrated ledgers, and the saved full-A1/full-H1/full-C1 A10 artifacts.

The candidate source is `problems/2026_gpu_scheduling/paper/output/document_paper_content_r2.tex`; the compiled PDF is `problems/2026_gpu_scheduling/paper/output/problem_b_paper_content_r2.pdf`. R1 and the historical V1/V2 PDFs remain unchanged.

`r2_metrics.json` contains the Q1 duration/worker statistics, complete-A10 FCFS/HOL/FILL metrics, worker strata, C0 six-pool metrics, input artifact identities, and the source-code check for SPT-HEAD-TIME. `r2_mapping.md` records reader-facing names, case IDs, file paths, and the C0 GS1 placement decision. `r2_acceptance.md` is the final PDF acceptance table.
