# Run from repository root with authorized official raw CSVs and .venv.
# Choose NEW --out paths for every rerun; historical directories are immutable.
# Core source for compared runs: 7d5d26b (source_sha256 recorded per summary).
for n in 16384 32768; do
  .venv/bin/python problems/2026_gpu_scheduling/experiments/run_m2b_benchmark.py \
    --out "outputs/q2-m2e-medium-${n}-20261015" --jobs "$n" \
    --theta-seconds 604800 --short-theta-seconds 604800 \
    --reservation-k 200 --event-mode shared-timer \
    --timeout-seconds 900 --max-rss-kib 4194304 \
    --policies SPT-FILL SPT-URGENT-HOL SPT-URGENT-TIME SPT-URGENT-FIXED SPT-URGENT-FLEX
  for child in "outputs/q2-m2e-medium-${n}-20261015"/a10-*; do
    .venv/bin/python problems/2026_gpu_scheduling/experiments/verify_m2a_pressure.py \
      --run "$child" --out "results/20261015-b-q2-m2e-01/$(basename "$child")-verified.json"
  done
  .venv/bin/python problems/2026_gpu_scheduling/experiments/analyze_m2e.py \
    --benchmark "outputs/q2-m2e-medium-${n}-20261015" \
    --verification-dir results/20261015-b-q2-m2e-01 \
    --out "results/20261015-b-q2-m2e-01/comparison-${n}.json"
done
.venv/bin/python problems/2026_gpu_scheduling/experiments/analyze_m2d_pairs.py \
  --benchmark outputs/q2-m2e-medium-32768-20261015 \
  --out results/20261015-b-q2-m2e-01/pairs-32768.json
# Original profile commands (before the code optimization):
for pair in 'time SPT-URGENT-TIME' 'fixed SPT-URGENT-FIXED' 'flex SPT-URGENT-FLEX'; do
  read -r tag policy <<< "$pair"
  .venv/bin/python -m cProfile \
    -o "outputs/q2-m2e-profile-before-20261015/${tag}.prof" \
    problems/2026_gpu_scheduling/experiments/run_m2a_pressure.py \
    --out "outputs/q2-m2e-profile-before-20261015/${tag}" \
    --jobs 16384 --theta-seconds 604800 --reservation-k 200 \
    --event-mode shared-timer --policies "$policy"
done
# To reproduce historical-vs-optimized bounded profile suite on final code,
# run the saved evidence driver with --out set to a NEW directory:
# .venv/bin/python results/20261015-b-q2-m2e-01/reproduce_profiles.py --out outputs/NEW-profile-suite

# Bounded 65,536 recovery after medium evidence and TIME GO decision.
.venv/bin/python problems/2026_gpu_scheduling/experiments/run_m2b_benchmark.py \
  --out outputs/q2-m2e-recovery-65536-time-20261015 --jobs 65536 \
  --theta-seconds 604800 --short-theta-seconds 604800 \
  --reservation-k 200 --event-mode shared-timer \
  --timeout-seconds 900 --max-rss-kib 4194304 --policies SPT-URGENT-TIME
.venv/bin/python problems/2026_gpu_scheduling/experiments/verify_m2a_pressure.py \
  --run outputs/q2-m2e-recovery-65536-time-20261015/a10-65536-theta604800-spt-urgent-time \
  --out results/20261015-b-q2-m2e-01/a10-65536-theta604800-spt-urgent-time-verified.json
.venv/bin/python problems/2026_gpu_scheduling/experiments/run_m2b_benchmark.py \
  --out outputs/q2-m2e-recovery-65536-remaining-20261015 --jobs 65536 \
  --theta-seconds 604800 --short-theta-seconds 604800 \
  --reservation-k 200 --event-mode shared-timer \
  --timeout-seconds 900 --max-rss-kib 4194304 \
  --policies SPT-URGENT-FIXED SPT-URGENT-FLEX SPT-FILL SPT-URGENT-HOL

# Once both recovery batches terminate, retain original benchmark records,
# independently replay each completed child, analyze and archive all evidence.
# Assembly refuses existing joined output/archive; use new paths on reproduction.
.venv/bin/python results/20261015-b-q2-m2e-01/assemble_recovery.py
python3 scripts/check_repo.py
python3 -m unittest discover -s tests -v
PYTHONPATH=problems/2026_gpu_scheduling/src .venv/bin/python -m unittest discover \
  -s problems/2026_gpu_scheduling/tests -v
git diff --check
