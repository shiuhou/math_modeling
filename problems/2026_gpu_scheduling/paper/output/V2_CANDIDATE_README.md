# Problem B V2 candidate

`problem_b_v2_candidate.pdf` is a bounded update built from the unchanged nine-page Baseline V1 candidate. It adds seven fresh merged-runtime checks and keeps the V1 evidence chain. The source index is `paper_sources_v2.json`.

The seven cases are run by `experiments/run_v2_integration_case.py` with the integrated `q3.py` and shared `simulate_pool`; exact metadata and comparisons are in `results/20261019-b-v2-integration-candidate/v2_runtime_equivalence.json`. Q2's fourteen read-only persisted replays are in `q2_persisted_replay.json`. These checks do not run a new scheduler or parameter search.

The PDF was compiled with Tectonic 0.17.0, is A4 and nine pages. Rendered page previews were inspected from `/tmp/v2preview-20261019`; this temporary preview directory is not part of the supplement. Final submission remains blocked pending team identity, human review, and confirmation of the complete AI-use record.
