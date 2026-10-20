#!/usr/bin/env python3
"""Verify small packaged evidence and regenerate tables without raw data or DES."""
import importlib.util
import csv
import json
import math
from pathlib import Path
import tempfile

ROOT=Path(__file__).resolve().parent
def main():
    src=ROOT/'problems/2026_gpu_scheduling/paper/final_publication'
    spec=importlib.util.spec_from_file_location('publication_generate',src/'generate.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    with tempfile.TemporaryDirectory(prefix='tables-',dir=ROOT) as tmp:
        mod.generate(ROOT,Path(tmp))
        for f in (src/'generated').glob('*.tex'):
            assert (Path(tmp)/f.name).read_bytes()==f.read_bytes(),f.name
    r=json.loads((ROOT/'results/20261019-paper-content-r2/r2_metrics.json').read_text())
    n=sum(x['jobs'] for x in r['q2_worker_strata'].values());assert n==111284
    for prefix,key in [('hol','SPT-HOL_C0'),('fill','SPT-FILL_full-A1')]:
        avg=sum(x['jobs']*x[f'{prefix}_mean_wait_h'] for x in r['q2_worker_strata'].values())/n
        assert math.isclose(avg,r['q2_a10_three_policy'][key]['mean_wait_h'],rel_tol=0,abs_tol=1e-12)
    assert sum(x[k] for x in r['q2_worker_strata'].values() for k in ['improved_hol','worsened_hol','unchanged'])==n
    total=sum(x['done90'] for x in r['q2_c0_six_pool'].values())
    data=json.loads((ROOT/'results/20261019-b-v2-integration-candidate/v2_runtime_equivalence.json').read_text())
    c0=next(x for x in data['cases'] if x['case']=='C0')
    assert total==c0['metrics']['cohorts']['ALL']['completed_at_horizon']==217578
    cases={x['case']:x for x in data['cases']}
    pairs=json.loads((ROOT/'results/20261020-final-publication/saved_timing_checks.json').read_text())
    historical=list(csv.DictReader((ROOT/'results/20261018-b-q3-v2-r1-6f2c8a10/paired.csv').open()))
    for row in pairs['records']:
        selector=row['historical_selector'];case=row['case']
        match=[x for x in historical if x['policy']==selector['policy'] and x['option']==selector['option'] and x['reference']=='M0' and (case=='C0' or float(x['sigma'])==selector['sigma'])]
        assert row['a10_later_finish_count']==int(next(x for x in match if x['cohort']=='A10')['harmed_jobs'])
        assert row['native_a100_wait_increase_count']==int(next(x for x in match if x['cohort']=='native_A100')['wait_harmed_jobs'])
        if case=='C0':continue
        allocation=row['allocation'];seconds=0
        for key,cap in [('A100-SXM4-80GB',2976),('A100-foreign',480)]:
            x=allocation[key];seconds+=x['window_gpu_seconds']
            assert abs(x['own_rate']-x['window_gpu_seconds']/(cap*7776000))<1e-14
            assert abs(x['own_rate']-cases[case]['metrics']['physical'][key]['gpu_allocation_rate_at_horizon'])<1e-14
        weighted=(2976*allocation['A100-SXM4-80GB']['own_rate']+480*allocation['A100-foreign']['own_rate'])/3456
        assert abs(weighted-seconds/(3456*7776000))<1e-14
    print('PASS: regenerated Tables 2-5, keyed winners, allocation, harm, worker aggregates and C0 completion sum')
if __name__=='__main__':main()
