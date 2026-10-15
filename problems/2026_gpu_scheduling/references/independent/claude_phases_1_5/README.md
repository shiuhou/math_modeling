# Claude phases 1–5 independent evidence archive

- **Stable source ID:** `claude-p1p5-562e82aa`
- **Archive:** `mcm_b_independent_research.tar.gz`
- **Archive SHA-256:** `562e82aaee5df02265fe75946051a713896de4e02571451a9f186fb51af2e6b1`
- **Archive size:** 41,507 bytes

This directory preserves one immutable copy of the Claude independent research package and its supplied verification record. It is a source archive and adoption crosswalk. It is not a second Q2 or Q3 implementation, and it does not change Q1, Q2, Q3 task files, raw data, reports, or saved experiment results.

## What is preserved

The archive is copied byte-for-byte. `MANIFEST.md` and `ERRATA.md` are extracted byte-for-byte from the archive; the external `claude_research_package_verification.json` is copied without edits. The 33 scripts remain inside the original tarball. They are not expanded into repository `src/`, `experiments/`, or `tests/`, and no package script was executed during intake. The package runner writes `results/core_run/`; any future reproduction must use a separately extracted working copy and must not write into this reference directory.

`SHA256SUMS` covers the six named files in this directory other than itself. `intake.json` records the input and extracted hashes, member and safety checks, fixed source commits reviewed, evidence identity, and scope limits.

## Evidence layers

The archive is read at three distinct layers:

1. **Prototype source and author claims.** The package scripts, logs, `MANIFEST.md`, and `ERRATA.md` are preserved as supplied. They describe prototype models, assumptions, and corrections; they are not repository interfaces or general theorems beyond their stated premises.
2. **External reproduction record.** `claude_research_package_verification.json` records an already performed local reproduction and targeted audit. Its `PASS` values, output matches, lower bounds, and ledger results are external evidence supplied with the package. Codex did not rerun the package or its large trace here.
3. **Formal repository migration/verification.** This intake only performs archive integrity, parsing, path/type, content-safety, and hash checks. No method was ported, no Q2/Q3 simulation was started, and no formal repository verification claim follows from this archive.

The only `PASS` claims made by this intake are the checks listed in `intake.json`. “Archived” must not be read as “Q2/Q3 formal validation complete.”

## Adoption crosswalk

### A. GPU-work weighted waiting lower bound

- **Candidate source:** `scripts/e1_area_tail.py`; the archived `scripts/lb3.py` is the older result that omits the post-trace tail.
- **External record:** the supplied verification records `560.5213678903029 h` for the A10 area-weighted lower bound and identifies `lb3.py` as superseded by E6.
- **Repository disposition:** Q1 already has the formal implementation and the `560.521 h` result. Do not migrate a second implementation from this package. Treat the package copy as an independent provenance and comparison source only.
- **Formal Q1 evidence:** [Q1 fixed commit](https://github.com/shiuhou/math_modeling/tree/7075317883808b1cd7f80cadf3980be291c69cf0), including `results/20261015-b-q1-capacity-bound/q1_capacity_bounds.json`.

### B. Job-count lower bound and truncated-gap accounting

- **Candidate sources:** `scripts/p2_countlb_all.py`, `scripts/p4_checks.py` in `truncated` mode, and ERRATA E1/E2.
- **Suggested use:** post-processing for the completed Q2 job timing evidence. The exact decomposition is accounting; the middle term is not a causal share and does not revise frozen headline metrics.
- **Prefix rule:** recompute the bound on the actual 65,536-job prefix. Do not apply the external 111,284-job `22.317930570033027 h` value to that prefix.
- **Formal Q2 evidence already saved:** [Q2 task record at its fixed commit](https://github.com/shiuhou/math_modeling/blob/508333e0216a18ef71797947bc670864a39f093d/notes/tasks/b-q2.md), [M2-E manifest](https://github.com/shiuhou/math_modeling/blob/508333e0216a18ef71797947bc670864a39f093d/results/20261015-b-q2-m2e-01/manifest.json), and [65,536 comparison](https://github.com/shiuhou/math_modeling/blob/508333e0216a18ef71797947bc670864a39f093d/results/20261015-b-q2-m2e-01/comparison-65536.json). These are preserved evidence from that commit, not rerun in this intake.

### C. SPT-HOL / SPT-skip / gang analysis

- Prototype ordering, scan budgets, and node approximations remain prototype details. The package labels its `sim_node.py` `sjf` policy as feasible-skip; it must not be renamed to formal SPT-HOL.
- Q2’s `SPT-URGENT-HOL` is a different policy contract from ordinary SPT-HOL. A method comparison still requires the same data, contract, and formal DES.
- No scheduler, placement rule, or parameter search is migrated by this commit.

### D. GS1 ratio matching

- **Candidate sources:** `scripts/p2_gs1.py`, `scripts/p2_gs1_validate.py`, `scripts/audit_v4.py`, and ERRATA E4.
- The reported `9,643/9,643` zero-wait construction and zero integer-ledger violations are a trace-specific constructive result, not a universal optimality theorem. Compatibility counterexamples in E4 remain part of the source record.
- Formal placement and cross-policy comparison remain future work. Withdrawn A8 is not restored.

### E. Q3 initial-batch-only borrowing candidate

- **Candidate sources:** `scripts/p4_lend60.py`, `scripts/e4_sigma_fixed.py`, and ERRATA E5.
- This is an independent candidate for the initial submission batch; it does not replace the current Q3 fixed-split mainline. The prototype’s 480 initial jobs differ from the formal 11,209-job full-trace fixed split.
- Do not apply the prototype `sigma*` directly to the formal fixed-split scenario. Any formal comparison must retain every original ID, native A100 resources, physical ledger, and JCT.
- The four Q3 reports remain in their original locations and are still the main Q3 rationale: [docs/4.md](https://github.com/shiuhou/math_modeling/blob/632435a0f616af916b7ba5474feb44f37df42817/docs/4.md), [貼上的文字 (1)(2).txt](https://github.com/shiuhou/math_modeling/blob/632435a0f616af916b7ba5474feb44f37df42817/docs/%E8%B2%BC%E4%B8%8A%E7%9A%84%E6%96%87%E5%AD%97%20(1)(2).txt), [貼上的文字 (2)(2).txt](https://github.com/shiuhou/math_modeling/blob/632435a0f616af916b7ba5474feb44f37df42817/docs/%E8%B2%BC%E4%B8%8A%E7%9A%84%E6%96%87%E5%AD%97%20(2)(2).txt), and [deep-research-report_q3.md](https://github.com/shiuhou/math_modeling/blob/632435a0f616af916b7ba5474feb44f37df42817/docs/deep-research-report_q3.md). The formal adoption table is [q3_model.md](https://github.com/shiuhou/math_modeling/blob/632435a0f616af916b7ba5474feb44f37df42817/problems/2026_gpu_scheduling/docs/q3_model.md), all referenced at Q3 commit `632435a0f616af916b7ba5474feb44f37df42817`.

## Data identity and availability

The package records Claude’s original `job_info_clean.csv` as `735bc06c3986b1d0c5932236f8685b7204463829118fc6a1d37030e253ed38e1`. The formal repository Q2/Q3 records use `ef14d696adc1b5c7847db49b41a068a998c8cd669e63922c92b3f1c3f32eedb0`. Both identities are retained; this intake does not alter raw data, claim the difference is only line endings, or perform a full data bridge. Existing semantic checks may be cited only within their saved scope.

Q2’s evidence archives are already saved in its formal results. Q3’s complete delivery ZIP remains a local-only artifact, and its cross-machine shared location is still an open delivery item. This source archive does not upload that large ZIP and does not rerun the Q3 trace.

## Deliberate non-actions and limits

This commit does not implement the five adoption candidates, start parameter search, launch a full simulation, rerun the 45 Q2 or 40 Q3 tests, or alter any frozen headline metric. The external verification JSON reports its own environment, reproduction differences, and limitations; those statements remain external claims. In particular, prototype A10 identical-unit approximations, SJF-skip naming, initial-batch premises, conditional sigma arithmetic, and all in-sample limits must remain visible to later adopters.

## Intake status

Archive hash, extracted-file hashes, JSON parsing, tar member safety, no-official-CSV/PDF check, sensitive-content review, SHA256SUMS verification, repository checks, and staged-scope checks are recorded in `intake.json`. The final commit SHA is intentionally not written here; it is supplied after commit so this file remains stable across the commit operation.
