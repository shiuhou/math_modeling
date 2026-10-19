# Paper Content R2 candidate

This is the revised 7-page A4 candidate for Paper Content R2. It is compiled from `document_paper_content_r2.tex` with Tectonic 0.17.0 and keeps the R1, V1, and historical V2 PDFs unchanged.

R2 adds the raw workload type statistics, C0 ratio-placement six-pool results in Question 2, complete-A10 FCFS/SPT-HOL/SPT-FILL comparison, the count lower bound and corrected gang condition, formal worker strata, code-checked SPT-HEAD-TIME wording, and the C0--C4 substitution table with common A100 denominator. All new numbers are read-only post-processing of formal CSVs, saved schedules, and saved ledgers; no scheduler or persisted replay was run.

The source and case mapping is in `results/20261019-paper-content-r2/r2_mapping.md`; metrics and input identities are in `r2_metrics.json`; the final PDF acceptance table is in `r2_acceptance.md`; build and visual-verification details are in `r2_build_provenance.json`.
