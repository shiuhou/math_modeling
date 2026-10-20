#!/usr/bin/env python3
"""Small existing tests plus a portable CLI fixture; never reads official trace."""
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent
PROBLEM=ROOT/'problems/2026_gpu_scheduling'
sys.path.insert(0,str(PROBLEM/'src'))
sys.path.insert(0,str(PROBLEM/'tests'))
def main():
    # The historical Q3PersistedCLI exercises a Git-dependent repository runner,
    # not this standalone package. Test unchanged Q3 core cases, then exercise
    # the package's portable CLI below on the synthetic fixture.
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(m) for m in ['test_baseline','test_gang_placement','test_q3.Q3Tests','test_q3_v2_shape','test_q2_bounds'])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
    import pandas as pd
    with tempfile.TemporaryDirectory(prefix='smoke-',dir=ROOT) as tmp:
        base=Path(tmp);data=base/'data';data.mkdir()
        nodes=[(1,'A10',1,128),(2,'A10',1,128),(500,'GPU-series-1',1,128),(501,'GPU-series-1',2,192)]+[(i,'A100-SXM4-80GB',8,128) for i in range(10,71)]
        jobs=[(1,'A10',8,1,2,0,10),(2,'A10',20,1,1,1,3),(3,'A100-SXM4-80GB',8,1,1,0,2),(4,'GPU-series-1',100,1,1,0,5),(5,'GPU-series-1',8,1,2,0,3)]
        pd.DataFrame(nodes,columns=['node_name','gpu_model','gpu_capacity_num','cpu_num']).to_csv(data/'node_info_df.csv',index=False)
        pd.DataFrame(jobs,columns=['job_name','gpu_model','cpu_request','gpu_request','worker_num','submit_time','duration']).to_csv(data/'job_info_clean.csv',index=False)
        for case in ['C0','C3','full-A1']:
            subprocess.run([sys.executable,'-I',str(ROOT/'reproduce.py'),'--case',case,'--data',str(data),'--output',str(base/case)],check=True)
            saved=pd.read_csv(base/case/'jobs.csv.gz')
            assert set(saved.job_name)==({1,2} if case=='full-A1' else {1,2,3,4,5})
            assert (saved.start>=saved.submit_time).all()
            assert (saved.finish-saved.start==saved.duration).all()
            metadata=json.loads((base/case/'metrics.json').read_text())
            assert metadata['case']==case
    for name in ['gpu_scheduling.simulator','gpu_scheduling.placement','gpu_scheduling.q3','gpu_scheduling.q3_v2']:
        path=Path(importlib.import_module(name).__file__).resolve();assert path.is_relative_to(ROOT),path
    print(json.dumps({'existing_tests':result.testsRun,'synthetic_CLI_cases':['C0','C3','full-A1'],'official_trace_executed':False,'status':'PASS'}))
if __name__=='__main__':main()
