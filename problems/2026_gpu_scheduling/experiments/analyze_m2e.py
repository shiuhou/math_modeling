#!/usr/bin/env python3
"""Read-only same-source bounded comparison using shared paired diagnostics."""
import argparse
import hashlib
import json
from pathlib import Path
from analyze_m2d_pairs import read_times, compare
from analyze_gang_starvation import read_times as read_gang, strata, pair


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--benchmark', type=Path, required=True)
    p.add_argument('--verification-dir', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        p.error('output must be new')
    b = json.loads((a.benchmark/'benchmark.json').read_text())
    rows, times, gangs, sources, configurations = [], {}, {}, [], []
    for r in b['records']:
        if r.get('status', 'PASS') != 'PASS':
            continue
        child = a.benchmark/r['child_output']
        verification = a.verification_dir/(child.name+'-verified.json')
        verified = json.loads(verification.read_text())
        if verified['status'] != 'PASS':
            raise ValueError('persisted replay failed')
        s = json.loads((child/'summary.json').read_text())
        sources.append((s['source_sha256'], s['data_sha256'], s['code_commit']))
        configurations.append((s['model'], s['jobs'],
                               {k: v for k, v in s['configuration'].items() if k != 'policies'}))
        policy = r['policy']
        if policy in times:
            raise ValueError('one jobs/theta group per comparison; duplicate policy')
        if not any(c['policy'] == policy and c['jobs'] == s['jobs'] and
                   c['capacity_replay'] == 'PASS' and c['reservation_replay'] == 'PASS'
                   for c in verified['checks']):
            raise ValueError('persisted replay does not cover this policy/jobs')
        path = child/f'{policy}_job_times.csv.gz'
        times[policy], gangs[policy] = read_times(path), read_gang(path)
        rows.append(dict(policy=policy, metrics=r['metrics'], gang=strata(gangs[policy]),
                         reservations=r['reservations'], cost=r['cost'],
                         scheduler_seconds=r['scheduler_seconds'], validation_seconds=r['validation_seconds'],
                         io_seconds=r['io_seconds'], peak_rss_kib=r['peak_rss_kib_process'],
                         schedule_sha256=r['schedule_sha256'],
                         verification_sha256=hashlib.sha256(verification.read_bytes()).hexdigest()))
    if not sources or any(s != sources[0] for s in sources):
        raise ValueError('comparison requires identical source/data versions')
    if any(c != configurations[0] for c in configurations):
        raise ValueError('comparison requires identical jobs and scheduling configuration')
    comparisons = []
    pairs = [('SPT-FILL', p) for p in times if p != 'SPT-FILL']
    pairs += [('SPT-URGENT-HOL', 'SPT-URGENT-TIME'),
              ('SPT-URGENT-TIME', 'SPT-URGENT-FIXED'),
              ('SPT-URGENT-TIME', 'SPT-URGENT-FLEX'),
              ('SPT-URGENT-FIXED', 'SPT-URGENT-FLEX')]
    for base, other in pairs:
        if base not in times or other not in times:
            continue
        # Check the original duration/worker grouping as well as timing inputs.
        if set(gangs[base]) != set(gangs[other]) or any(
            (gangs[base][j]['duration'], gangs[base][j]['worker_num']) !=
            (gangs[other][j]['duration'], gangs[other][j]['worker_num']) for j in gangs[base]):
            raise ValueError('gang input mismatch')
        comparisons.append(dict(baseline=base, policy=other,
                                overall=compare(times[base], times[other]),
                                gang=pair(gangs[base], gangs[other])))
    output = dict(kind='m2e_same_source_comparison', status='PASS',
                  configuration=b['configuration'], source_sha256=sources[0][0],
                  data_sha256=sources[0][1], source_commit=sources[0][2],
                  strategies=rows, paired=comparisons,
                  limitation='Official A10 prefix at exploratory theta=168h; no full-trace extrapolation.')
    a.out.write_text(json.dumps(output, indent=2)+'\n')
    print(a.out)

if __name__ == '__main__':
    main()
