#!/usr/bin/env python3
"""Profile the existing DES (optionally exact Git source) on an official prefix.

No alternative scheduler is maintained: --revision loads the simulator bytes
from Git with the same current, hash-recorded placement and validation modules.
Use only revisions with unchanged dependencies. Outputs are new compact JSON.
"""
from __future__ import annotations
import argparse
import cProfile
import hashlib
import json
from pathlib import Path
import pstats
import resource
import subprocess
import sys
import time
import types

PROBLEM = Path(__file__).resolve().parents[1]
REPO = PROBLEM.parents[1]
sys.path.insert(0, str(PROBLEM / 'src'))
from gpu_scheduling.data import read_data
from gpu_scheduling.simulator import simulate_pool
from gpu_scheduling.validation import validate_reservations


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--jobs', type=int, default=8192)
    p.add_argument('--theta-seconds', type=int, default=604800)
    p.add_argument('--policy', required=True)
    p.add_argument('--revision')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists() or a.jobs <= 0:
        p.error('output must be new and jobs positive')
    path = PROBLEM / 'src/gpu_scheduling/simulator.py'
    source = path.read_bytes()
    simulator = simulate_pool
    if a.revision:
        source = subprocess.check_output(['git', 'show', f'{a.revision}:{path.relative_to(REPO)}'], cwd=REPO)
        for dependency in ('placement.py', 'validation.py'):
            dep = path.with_name(dependency)
            old = subprocess.check_output(['git', 'show', f'{a.revision}:{dep.relative_to(REPO)}'], cwd=REPO)
            if old != dep.read_bytes():
                raise ValueError(f'changed dependency: {dependency}')
        module = types.ModuleType('gpu_scheduling._profile_revision')
        module.__package__ = 'gpu_scheduling'
        exec(compile(source, str(path), 'exec'), module.__dict__)
        simulator = module.simulate_pool
    nodes, jobs, hashes = read_data(PROBLEM / 'data/raw')
    nodes = nodes[nodes.gpu_model == 'A10']
    jobs = jobs[jobs.gpu_model == 'A10'].head(a.jobs)
    profiler = cProfile.Profile()
    started = time.perf_counter()
    profiler.enable()
    result = simulator(nodes, jobs, a.policy, theta_seconds=a.theta_seconds,
                       reservation_k=200, event_mode='shared-timer')
    profiler.disable()
    elapsed = time.perf_counter() - started
    valid_started = time.perf_counter()
    validate_reservations(nodes, result['jobs'], result)
    validation_seconds = time.perf_counter() - valid_started
    stats = pstats.Stats(profiler)
    functions = []
    for (file, line, function), (primitive, calls, self_time, cumulative, callers) in stats.stats.items():
        if file.endswith(('simulator.py', 'placement.py')) or 'remove' in function:
            functions.append(dict(file=Path(file).name, line=line, function=function,
                                  calls=calls, self_seconds=self_time, cumulative_seconds=cumulative))
    schedule = {k: result[k].tolist() for k in ('starts', 'ends')}
    schedule['plans'] = result['plans']
    decision_times = set(result['jobs'].submit_time.tolist()) | set(result['ends'].tolist())
    decision_times |= {e['time'] for e in result['events'] if e['kind'] in ('timer_threshold', 'reservation_issued')}
    output = dict(kind='m2e_scheduler_profile', simulator_revision=a.revision,
                  current_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
                  simulator_sha256=hashlib.sha256(source).hexdigest(), data_sha256=hashes,
                  configuration=dict(jobs=a.jobs, policy=a.policy, theta_seconds=a.theta_seconds,
                                     event_mode='shared-timer', reservation_k=200, placement='FF-id'),
                  scheduler_profiled_seconds=elapsed, validation_seconds=validation_seconds,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  cost=result['cost'], reservations=len(result['reservations']),
                  event_count=len(result['events']), timer_events=sum(e['kind']=='timer_threshold' for e in result['events']),
                  distinct_decision_times=len(decision_times),
                  schedule_sha256=digest(schedule), events_sha256=digest(result['events']),
                  reservations_sha256=digest(result['reservations']), independent_validation='PASS',
                  functions=sorted(functions, key=lambda r: r['cumulative_seconds'], reverse=True))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(output, indent=2)+'\n')
    print(a.out)

if __name__ == '__main__':
    main()
