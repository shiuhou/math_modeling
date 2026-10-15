#!/usr/bin/env python3
"""Verify persisted Q3 routing, original IDs, node ledgers and independent metrics."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time

PROBLEM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROBLEM/'src'))
import pandas as pd
from gpu_scheduling.data import native, read_data
from gpu_scheduling.q3 import Config, POLICIES
from gpu_scheduling.q3_validation import verify_schedule, verify_metrics, verify_comparison, require


def verify(data, run):
    started = time.perf_counter()
    nodes, jobs, hashes = read_data(data)
    manifest = json.loads((run/'run.json').read_text())
    require(manifest['status'] == 'PASS', 'Incomplete run')
    require(manifest['data_sha256'] == hashes, 'Raw data hashes')
    require(manifest['jobs'] == len(jobs) and manifest['nodes'] == len(nodes), 'Full trace scope')
    for file, digest in manifest['outputs'].items():
        require(hashlib.sha256((run/file).read_bytes()).hexdigest() == digest, 'Output hash: '+file)
    for file, digest in manifest['source_sha256'].items():
        require(hashlib.sha256((run/'source'/file).read_bytes()).hexdigest() == digest, 'Source snapshot hash: '+file)
    config = Config(**json.loads((run/'config.json').read_text()))
    require(config.dictionary() == manifest['configuration'], 'Frozen configuration')
    metrics = json.loads((run/'metrics.json').read_text())
    recovery = json.loads((run/'recovery.json').read_text())
    for policy in POLICIES:
        require(all(recovery.get(policy+'/'+key, '').startswith('PASS') for key in ['B0', 'K_disabled']), 'M0 recovery')
    checks = {}
    for policy in POLICIES:
        frames = {}
        for label, c in [('M0', replace(config, compatibility=False)), ('M1', config)]:
            f = pd.read_csv(run/f'{policy}_{label}_jobs.csv.gz')
            ledger = pd.read_csv(run/f'{policy}_{label}_placements.csv.gz')
            key = policy+'/'+label
            checks[key] = {'schedule': verify_schedule(nodes, jobs, f, ledger, c),
                           'metrics': verify_metrics(nodes, f, c, metrics[policy][label])}
            frames[label] = f
            print(key+': raw routing, physical replay, metrics PASS', flush=True)
        checks[policy+'/paired'] = verify_comparison(frames['M0'], frames['M1'], config.horizon_seconds, metrics[policy]['paired_M1_minus_M0'])
    return native({'status': 'PASS', 'checks': checks, 'seconds': time.perf_counter()-started,
                   'sensitivity_decision': 'GO for predeclared small single-factor study; no performance superiority requirement'})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', type=Path, default=PROBLEM/'data/raw')
    p.add_argument('--run', type=Path, required=True)
    args = p.parse_args()
    result = verify(args.data, args.run)
    (args.run/'verified.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
