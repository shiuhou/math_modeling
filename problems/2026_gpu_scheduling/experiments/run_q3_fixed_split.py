#!/usr/bin/env python3
"""Full-trace M0 recovery and M1 fixed substitution; no sensitivity search."""
import argparse
from dataclasses import replace
import hashlib
import json
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import time

PROBLEM = Path(__file__).resolve().parents[1]
REPO = PROBLEM.parents[1]
sys.path.insert(0, str(PROBLEM / 'src'))
import numpy as np
import pandas as pd
from gpu_scheduling.data import native, read_data
from gpu_scheduling.q3 import Config, POLICIES, compare, describe, simulate
from gpu_scheduling.simulator import simulate_pool


def write_json(path, value):
    path.write_text(json.dumps(native(value), ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def direct_baseline(nodes, jobs, policy):
    frames, rows = [], []
    for model, sub in jobs.groupby('gpu_model', sort=True):
        pool = nodes[nodes.gpu_model == model].sort_values('node_name').reset_index(drop=True)
        r = simulate_pool(pool, sub, policy)
        f = r['jobs'].copy(); f['start'], f['finish'] = r['starts'], r['ends']; frames.append(f)
        rows.extend((int(j), int(pool.node_name.iloc[n]), int(w)) for j, plan in zip(f.job_name, r['plans']) for n, w in plan)
    return pd.concat(frames).sort_values('job_name').reset_index(drop=True), pd.DataFrame(rows, columns=['job_name', 'node_name', 'workers']).sort_values(['job_name', 'node_name']).reset_index(drop=True)


def exact_schedule(a, al, b, bl):
    pd.testing.assert_frame_equal(a[['job_name', 'start', 'finish']].sort_values('job_name').reset_index(drop=True), b[['job_name', 'start', 'finish']].sort_values('job_name').reset_index(drop=True))
    pd.testing.assert_frame_equal(al.sort_values(['job_name', 'node_name']).reset_index(drop=True), bl.sort_values(['job_name', 'node_name']).reset_index(drop=True))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', type=Path, default=PROBLEM/'data/raw')
    p.add_argument('--config', type=Path, default=PROBLEM/'configs/q3_fixed_split_v1.json')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--historical-baseline', type=Path, help='Optional verified full baseline artifact directory')
    args = p.parse_args()
    if args.out.exists():
        p.error('Choose a new output directory')
    cfg = Config(**json.loads(args.config.read_text()))
    started = time.perf_counter()
    nodes, jobs, hashes = read_data(args.data)
    args.out.mkdir(parents=True)
    write_json(args.out/'config.json', cfg.dictionary())
    # Include executable dirty sources, tests and model documentation, not just a commit SHA.
    files = sorted((PROBLEM/'src').rglob('*.py')) + sorted((PROBLEM/'experiments').glob('*.py')) + sorted((PROBLEM/'tests').glob('*.py')) + [PROBLEM/'docs/q3_model.md']
    for source in files:
        dest = args.out/'source'/source.relative_to(REPO)
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, dest)
    manifest = {'kind': 'q3_fixed_split_v1', 'scope': 'full_trace', 'configuration': cfg.dictionary(),
                'data_sha256': hashes, 'jobs': len(jobs), 'nodes': len(nodes),
                'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
                'git_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=REPO, text=True).strip()),
                'source_sha256': {str(f.relative_to(REPO)): digest(f) for f in files},
                'command': sys.argv, 'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__, 'platform': platform.platform()},
                'status': 'RUNNING', 'durations_seconds': {}, 'outputs': {}}
    write_json(args.out/'run.json', manifest)
    results = {}; recovery = {}
    for policy in POLICIES:
        tick = time.perf_counter()
        direct, direct_ledger = direct_baseline(nodes, jobs, policy)
        print(f'{policy}: direct M0 complete', flush=True)
        zero = replace(cfg, donor_nodes=0)
        off = replace(cfg, compatibility=False)
        for label, c in [('B0', zero), ('K_disabled', off)]:
            f, ledger = simulate(nodes, jobs, policy, c)
            exact_schedule(direct, direct_ledger, f, ledger)
            recovery[f'{policy}/{label}'] = 'PASS: exact all-job start/finish and physical placement'
            print(f'{policy}: {label} exact recovery PASS', flush=True)
        # f is exactly M0; retaining provenance labels disabled is intentional.
        scenarios = [('M0', f, ledger, off)]
        f1, l1 = simulate(nodes, jobs, policy, cfg)
        scenarios.append(('M1', f1, l1, cfg))
        results[policy] = {}
        for label, frame, placements, c in scenarios:
            frame.to_csv(args.out/f'{policy}_{label}_jobs.csv.gz', index=False, compression='gzip')
            placements.to_csv(args.out/f'{policy}_{label}_placements.csv.gz', index=False, compression='gzip')
            results[policy][label] = describe(nodes, frame, c)
        results[policy]['paired_M1_minus_M0'] = compare(scenarios[0][1], f1, cfg.horizon_seconds)
        if args.historical_baseline:
            hist = pd.read_csv(args.historical_baseline/f'{policy}_job_times.csv.gz')
            hist_l = pd.read_csv(args.historical_baseline/f'{policy}_node_placements.csv.gz')
            exact_schedule(direct, direct_ledger, hist, hist_l)
            recovery[f'{policy}/historical_normalized_schedule'] = 'PASS'
            # The historical horizon differs; recompute and compare every persisted baseline metric.
            old_rows = json.loads((args.historical_baseline/'baseline_metrics.json').read_text())
            from gpu_scheduling.evaluation import metrics
            for row in old_rows:
                if row['policy'] != policy:
                    continue
                model = row['gpu_model']
                sub = direct if model == 'ALL' else direct[direct.gpu_model == model]
                pool = nodes if model == 'ALL' else nodes[nodes.gpu_model == model]
                calc = metrics({'jobs': sub, 'starts': sub.start.to_numpy(), 'ends': sub.finish.to_numpy()}, pool, 7775878)
                for key, value in calc.items():
                    if not np.isclose(value, row[key], rtol=1e-11, atol=1e-10):
                        raise AssertionError('Historical metric mismatch: '+key)
            recovery[f'{policy}/historical_metrics_H7775878'] = 'PASS'
            manifest['historical_sha256'] = {f.name: digest(f) for f in args.historical_baseline.iterdir() if f.is_file()}
        manifest['durations_seconds'][policy] = time.perf_counter()-tick
        write_json(args.out/'metrics.json', results); write_json(args.out/'recovery.json', recovery)
        print(f'{policy}: M1 persisted; {manifest["durations_seconds"][policy]:.2f}s', flush=True)
    manifest['status'] = 'PASS'; manifest['total_seconds'] = time.perf_counter()-started
    manifest['outputs'] = {f.name: digest(f) for f in args.out.iterdir() if f.is_file() and f.name != 'run.json'}
    write_json(args.out/'run.json', manifest)


if __name__ == '__main__':
    main()
