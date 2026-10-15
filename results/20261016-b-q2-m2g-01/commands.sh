# M2-G reproducible commands
# Working directory: repository root
# Use the repository venv; unset app-injected PYTHONHOME/PYTHONPATH.
# G1
env -u PYTHONHOME -u PYTHONPATH PYTHONPATH=problems/2026_gpu_scheduling/src .venv/bin/python problems/2026_gpu_scheduling/experiments/run_m2b_benchmark.py --data problems/2026_gpu_scheduling/data/raw --out outputs/q2-m2g-g1-65536-20261016-spt-hol --model A10 --jobs 65536 --theta-seconds 604800 --short-theta-seconds 604800 --event-mode shared-timer --reservation-k 200 --timeout-seconds 900 --max-rss-kib 4194304 --policies SPT-HOL
# G2/G3: same command with jobs 111284, policy/output respectively SPT-HOL/q2-m2g-g2-111284-20261016-spt-hol and SPT-FILL/q2-m2g-g3-111284-20261016-spt-fill.
# Independent replay: verify_m2a_pressure.py --data problems/2026_gpu_scheduling/data/raw --run <child-output> --out <run>-verified.json
# Lower bound/decomposition: analyze_m2f_bounds.py --timing-dir <child-output> --jobs <count> --policies <policy> --comparison /tmp/q2-m2g-empty.json --out results/<per-run>
# Comparison assembly: analyze_m2g.py --archive results/20261015-b-q2-m2e-01/evidence-65536.tar.gz --g1-timing <g1-child> --g2-timing <g2-child> --g3-timing <g3-child> --g1-decomposition <g1-decomp> --g2-decomposition <g2-decomp> --g3-decomposition <g3-decomp> --out results/20261016-b-q2-m2g-01
