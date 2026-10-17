import unittest
import tempfile
from pathlib import Path
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from run_gs1_placement_matrix import replay_ledger
from gpu_scheduling.placement import plan_ratio_matching

class RevisionChecks(unittest.TestCase):
    def test_fallback_tie(self):
        p = plan_ratio_matching(np.array([8,8]), np.array([12800,12800]), 1,3200,1, order=[1,0])
        self.assertEqual(p.nodes, ((0,1),))

    def fixture(self):
        nodes = pd.DataFrame(dict(node_name=[20,30],gpu_model=['X']*2,gpu_capacity_num=[1,1],cpu_units=[100,100]))
        jobs = pd.DataFrame(dict(job_name=[1,2],gpu_model=['X']*2,gpu_request=[1,1],cpu_units=[100,100],worker_num=[2,2],submit_time=[0,10],duration=[10,10]))
        times = jobs.copy(); times['start']=[0,10]; times['finish']=[10,20]; times['wait']=[0,0]
        ledger = pd.DataFrame(dict(job_name=[1,1,2,2],node_name=[20,30,20,30],workers=[1,1,1,1]))
        return nodes,jobs,times,ledger

    def replay(self, nodes,jobs,times,ledger):
        with tempfile.TemporaryDirectory() as d:
            t=Path(d)/'t.csv'; l=Path(d)/'l.csv'
            times.to_csv(t,index=False); ledger.to_csv(l,index=False)
            return replay_ledger(nodes,jobs,t,l)['status']

    def test_valid_same_time_release(self):
        self.assertEqual(self.replay(*self.fixture()), 'PASS')

    def test_fault_injection(self):
        for fault in ['duplicate_pair','duration','duplicate_id','missing_id','early','zero','fraction','negative','raw_cpu','raw_gpu','raw_worker','raw_submit','raw_duration','nan','missing_column','unknown_node']:
            with self.subTest(fault=fault):
                n,j,t,l=self.fixture()
                if fault=='duplicate_pair': l.loc[1,'node_name']=20
                if fault=='duration': t.loc[0,'finish']=1
                if fault=='duplicate_id': t=pd.concat([t,t.iloc[:1]])
                if fault=='missing_id': t=t.iloc[:1]
                if fault=='early': t.loc[1,['start','finish']]=[9,19]
                if fault=='zero': l.loc[0,'workers']=0
                if fault=='fraction': l['workers']=l.workers.astype(float);l.loc[0,'workers']=1.5
                if fault=='negative': l.loc[0,'workers']=-1
                if fault.startswith('raw_'):
                    c={'raw_cpu':'cpu_units','raw_gpu':'gpu_request','raw_worker':'worker_num','raw_submit':'submit_time','raw_duration':'duration'}[fault];t.loc[0,c]+=1
                if fault=='nan': t.loc[0,'start']=float('nan')
                if fault=='missing_column': t=t.drop(columns='cpu_units')
                if fault=='unknown_node': l.loc[0,'node_name']=99
                self.assertEqual(self.replay(n,j,t,l), 'FAIL')

    def test_numeric_node_names_and_ff_order(self):
        from gpu_scheduling.simulator import simulate_pool
        n,j,_,_=self.fixture()
        n['node_name']=[100,2]; n['gpu_capacity_num']=[8,8]; n['cpu_units']=[12800,12800]
        j=j.iloc[:1].copy();j['gpu_request']=1;j['cpu_units']=3200;j['worker_num']=1
        ratio=simulate_pool(n,j,'FCFS-HOL',placement='ratio',node_order=[1,0])
        # Internal arrays are sorted as [2,100], irrespective of input row order.
        self.assertEqual(ratio['plans'],[[(0,1)]])
        ff=simulate_pool(n,j,'FCFS-HOL',node_order=[1,0])
        self.assertEqual(ff['plans'],[[(1,1)]])

    def test_ff_matches_source_commit_small(self):
        import subprocess, types
        from gpu_scheduling.simulator import simulate_pool
        from gpu_scheduling.placement import plan_first_fit
        repo=Path(__file__).resolve().parents[3]
        module=types.ModuleType('gpu_scheduling.old_simulator');module.__package__='gpu_scheduling'
        source=subprocess.check_output(['git','show','a20d73f:problems/2026_gpu_scheduling/src/gpu_scheduling/simulator.py'],cwd=repo,text=True)
        exec(source,module.__dict__)
        n,j,_,_=self.fixture()
        for policy in ['FCFS-HOL','SPT-HOL']:
            for order in [None,[1,0]]:
                old=module.simulate_pool(n,j,policy,node_order=order,theta_seconds=604800)
                new=simulate_pool(n,j,policy,node_order=order,theta_seconds=604800)
                self.assertEqual(old['starts'].tolist(),new['starts'].tolist())
                self.assertEqual(old['plans'],new['plans'])
                self.assertEqual(old['events'],new['events'])
        import ast,inspect
        text=subprocess.check_output(['git','show','a20d73f:problems/2026_gpu_scheduling/src/gpu_scheduling/placement.py'],cwd=repo,text=True)
        old=next(x for x in ast.parse(text).body if isinstance(x,ast.FunctionDef) and x.name=='plan_first_fit')
        new=ast.parse(inspect.getsource(plan_first_fit)).body[0]
        self.assertEqual(ast.dump(old),ast.dump(new))
