# Paper Content R2 Correctness Patch

This is a separate corrected candidate layered on the validated R2 candidate. The original `problem_b_paper_content_r2.pdf` remains unchanged with SHA256 `26a0a268e7c89439764388d94dd5b21708c17e35a810d51626e2e74085593f0f`. The corrected PDF is `problem_b_paper_content_r2_correctness_patch.pdf`.

The patch corrects the FCFS/SPT-HOL versus Shape-filtered winner wording, regenerates the Q3 C0--C4 table directly from `v2_runtime_equivalence.json` case keys, replaces stale C0 all-JCT/completion values, separates partition-own A100 rates from full-pool contributions, retains the gang mechanism qualification, replaces JSON-looking waiting decomposition with a mathematical equality, and sets header/footer font commands to 11 pt.

No scheduler or replay was run. The generator, formal source fields, old R2 FAIL record, new PDF checks, and page review are in `results/20261019-paper-content-r2-correctness-patch/`.
