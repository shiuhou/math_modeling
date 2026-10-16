#!/usr/bin/env python3
"""Bounded old/new verifier RSS curve, using actual persisted/schema-2 evidence.

Run each revision/case in a separate process. A historical source is loaded
with observability-only hooks; scheduling and evidence are never modified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time
import types
import numpy as np
import pandas as pd

PROBLEM = Path(__file__).resolve().parents[1]
REPO = PROBLEM.parents[1]
sys.path.insert(0, str(PROBLEM / 'src'))
sys.path.insert(0, str(PROBLEM / 'experiments'))
from gpu_scheduling.data import read_data, prepare_data
from gpu_scheduling.simulator import simulate_pool
from gpu_scheduling.validation import validate_reservations
from run_m2a_pressure import PhaseLog


def load_run(path):
    summary = json.loads((path / 'summary.json').read_text())
    nodes, jobs, hashes = read_data(PROBLEM / 'data/raw')
    assert hashes == summary['data_sha256']
    nodes = nodes[nodes.gpu_model == summary['model']].sort_values('node_name').reset_index(drop=True)
    jobs = jobs[jobs.gpu_model == summary['model']].head(summary['jobs'])
    policy = summary['results'][0]['policy']
    frame = pd.read_csv(path / f'{policy}_job_times.csv.gz')
    jobs = jobs.set_index('job_name').loc[frame.job_name].reset_index()
    placements = pd.read_csv(path / f'{policy}_node_placements.csv.gz')
    job_ids = {int(j): i for i, j in enumerate(frame.job_name)}
    node_ids = {int(n): i for i, n in enumerate(nodes.node_name)}
    plans = [[] for _ in range(len(jobs))]
    for jid, nid, w in placements.itertuples(index=False, name=None):
        plans[job_ids[int(jid)]].append((node_ids[int(nid)], int(w)))
    result = json.loads((path / f'{policy}_reservations.json').read_text())
    result.update(starts=frame.start.to_numpy(), ends=frame.finish.to_numpy(), plans=plans)
    return nodes, jobs, result


def synthetic(count, node_count):
    # Every pair creates one real HOL promise, then fulfills it before the next
    # pair arrives. Extra nodes have zero CPU capacity; vectors retain pool size.
    nodes = pd.DataFrame({'node_name': range(node_count), 'gpu_model': ['X'] * node_count,
                          'gpu_capacity_num': [1] * node_count,
                          'cpu_num': [1, 1] + [0] * (node_count - 2)})
    rows = []
    for k in range(count):
        for offset, workers, duration in ((0, 1, 2), (1, 2, 1)):
            rows.append(dict(job_name=2*k+offset, gpu_model='X', gpu_request=1,
                             cpu_request=1., worker_num=workers, submit_time=3*k, duration=duration))
    nodes, jobs = prepare_data(nodes, pd.DataFrame(rows))
    result = simulate_pool(nodes, jobs, 'SPT-URGENT-HOL', theta_seconds=0)
    assert len(result['reservations']) == count
    return nodes, result['jobs'], result


def historical(revision, progress):
    path = 'problems/2026_gpu_scheduling/src/gpu_scheduling/validation.py'
    source = subprocess.check_output(['git', 'show', f'{revision}:{path}'], cwd=REPO, text=True)
    source_hash = hashlib.sha256(source.encode()).hexdigest()
    source = source.replace('    for item in events:', '''    def report(action, count):
        progress("reservation_replay", action, events_processed=count,
                 promises_issued=len(issued_ids), promises_completed=len(fulfilled_ids),
                 live_dense_contexts=sum(c["future_g"] is not None for c in contexts.values()),
                 live_dense_bytes=sum(c["future_g"].nbytes + c["future_c"].nbytes
                                      for c in contexts.values() if c["future_g"] is not None),
                 retained_active_set_bytes=sum(sys.getsizeof(c["active_at_issue"]) for c in contexts.values()))
    report("begin", 0)
    for event_index, item in enumerate(events):
        if event_index and event_index % 4096 == 0:
            report("progress", event_index)''')
    source = source.replace('    if active_promise_id is not None:\n        raise AssertionError("pending promise', '    report("events_end", len(events))\n    if active_promise_id is not None:\n        raise AssertionError("pending promise')
    module = types.ModuleType('gpu_scheduling._historical_validation')
    module.__package__ = 'gpu_scheduling'
    module.progress = progress
    module.sys = sys
    exec(compile(source, f'<{revision}:validation.py>', 'exec'), module.__dict__)
    return module.validate_reservations, source_hash


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path)
    p.add_argument('--synthetic-promises', type=int)
    p.add_argument('--nodes', type=int, default=2494)
    p.add_argument('--revision', default='current')
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if args.out.exists(): p.error('choose a fresh output directory')
    args.out.mkdir(parents=True)
    nodes, jobs, result = load_run(args.run) if args.run else synthetic(args.synthetic_promises, args.nodes)
    phase = PhaseLog(args.out / 'phase_log.jsonl')
    phase('input_ready', 'end', jobs=len(jobs), promises=len(result['reservations']), nodes=len(nodes))
    if args.revision == 'current':
        verifier = lambda n, j, r: validate_reservations(n, j, r, progress=phase)
        source_hash = hashlib.sha256((PROBLEM / 'src/gpu_scheduling/validation.py').read_bytes()).hexdigest()
    else:
        verifier, source_hash = historical(args.revision, phase)
    started = time.perf_counter()
    verifier(nodes, jobs, result)
    elapsed = time.perf_counter() - started
    phase('validation', 'end')
    output = dict(status='PASS', revision=args.revision, validation_seconds=elapsed,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  jobs=len(jobs), nodes=len(nodes), promises=len(result['reservations']), events=len(result['events']),
                  source_sha256=source_hash,
                  event_sha256=hashlib.sha256(json.dumps(result['events'], sort_keys=True).encode()).hexdigest(),
                  schedule_sha256=hashlib.sha256(json.dumps(dict(starts=result['starts'].tolist(),
                      ends=result['ends'].tolist(), plans=result['plans']), sort_keys=True).encode()).hexdigest())
    (args.out / 'summary.json').write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps(output))

if __name__ == '__main__': main()
