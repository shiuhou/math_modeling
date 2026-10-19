# Paper Content R1: official-question mapping

| Official question | Model / algorithm in the paper | Formal evidence used | Visible paper location |
|---|---|---|---|
| Q1 workload and capacity | Six isolated pools; submitted work ratios; immediate-start overlap demand; concentration, duration, relative phase, and node-shape diagnostics | `results/20261014-b-q1-intake-4a8f8f2b/` Q1 tables and raw formal-run CSV; generated `r1_figures/fig1_demand.pdf` and `fig1_data_patterns.pdf` | Q1, Table 1, Figures 1--2 |
| Q2 scheduling | SPT-HOL (historical SJF-HOL alias), atomic gang admission, HOL, GS1 ratio placement, SPT-FILL comparison, count lower bound | `results/20261019-b-v2-integration-candidate/v2_runtime_equivalence.json`; `results/20261018-b-q2-v2-r1-01/`; GS1 corrected comparison under `results/20261018-b-gs1-placement-v2-r1/` | Q2, Algorithm 1, equations (2)--(4), Table 1, GS1 paragraph |
| Q3 substitution | V1 fixed-split R0 sensitivity and V2 R-shape fixed physical counterfactual; common-queue sigma reasoning; native/foreign full-pool allocation | `results/20261018-b-q3-v2-r1-6f2c8a10/main_table.json`; R-shape metric ledgers in `results/20261017-b-q3-v2-shape-a17c4e9d/`; V1 sensitivity figure | Q3, Table 2, Figure 3, trade-off paragraphs |
| Reproducibility limits | Two input identities, exact timing windows, saved-ledger replay status, AI-use record | `results/20261019-paper-content-r1/input_comparison.json`, `r1_metrics.json`, V2 integration and replay manifests | Data/validation paragraph, conclusion, AI statement |
