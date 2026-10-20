# All 14 children were run serially with --timeout-seconds 900 and --max-rss-kib 4194304.
# 65k: replace JOBS with 65536; full: replace JOBS with 111284.
.venv/bin/python problems/2026_gpu_scheduling/experiments/run_m2b_benchmark.py --jobs JOBS --theta-seconds 604800 --short-theta-seconds 604800 --reservation-k K --event-mode MODE --policies POLICY --timeout-seconds 900 --max-rss-kib 4194304 --out outputs/q2-v2-ID
# Post-process all persisted timing files:
PYTHONPATH=problems/2026_gpu_scheduling/src .venv/bin/python problems/2026_gpu_scheduling/experiments/analyze_v2.py --repo-root . --out results/20261017-b-q2-v2-01/computed-v2 --runs ...
