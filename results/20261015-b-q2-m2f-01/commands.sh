#!/bin/sh
set -eu
# Run from the repository root. Set PYTHON to the approved environment if needed.
PYTHON=${PYTHON:-python3}
OUT=${OUT:-results/20261015-b-q2-m2f-reproduction}
PYTHONPATH=problems/2026_gpu_scheduling/src
export PYTHONPATH
# The recorded run used /home/shiuhou/mm/math_modeling-b-q2/.venv/bin/python.
env -u PYTHONHOME -u PYTHONPATH PYTHONPATH="$PYTHONPATH" "$PYTHON" \
  problems/2026_gpu_scheduling/experiments/analyze_m2f_bounds.py \
  --repo-root . \
  --archive results/20261015-b-q2-m2e-01/evidence-65536.tar.gz \
  --comparison results/20261015-b-q2-m2e-01/comparison-65536.json \
  --out "$OUT"
