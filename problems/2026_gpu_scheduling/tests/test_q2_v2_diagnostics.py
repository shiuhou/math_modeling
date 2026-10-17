"""Counter scope contract; no formal scheduler workload is executed."""
import unittest
import pandas as pd
from gpu_scheduling.simulator import simulate_pool

class DiagnosticScope(unittest.TestCase):
    def test_cross_epoch_rechecks_are_not_same_epoch_redundancy(self):
        nodes = pd.DataFrame(dict(node_name=[0], gpu_model=['X'], gpu_capacity_num=[1], cpu_units=[100]))
        jobs = pd.DataFrame(dict(job_name=[0,1,2,3], gpu_model=['X']*4,
            gpu_request=[1]*4, cpu_units=[100]*4, worker_num=[1]*4,
            submit_time=[0,1,1,2], duration=[10,20,30,40]))
        # At t=1, job 2 is the only bypass attempt. At t=2, jobs 2 and 3
        # are each tried once. Later epochs add more cross-epoch retries;
        # no successful bypass exists, hence no seen.clear/retry at any epoch.
        on = simulate_pool(nodes, jobs, 'SPT-FILL', event_mode='arrival-completion-only')
        off = simulate_pool(nodes, jobs, 'SPT-FILL', event_mode='arrival-completion-only', diagnostics=False)
        c = on['cost']
        self.assertGreater(c['repeated_candidate_attempts'], 0)
        self.assertEqual(c['candidate_attempts'], c['unique_candidate_ids'] + c['repeated_candidate_attempts'])
        self.assertEqual(on['starts'].tolist(), [0,10,30,60])
        self.assertEqual(on['plans'], off['plans'])
        self.assertEqual(on['events'], off['events'])
        self.assertIsNone(off['cost']['unique_candidate_ids'])
        self.assertIsNone(off['cost']['repeated_candidate_attempts'])
        self.assertEqual(c['candidate_attempts'], off['cost']['candidate_attempts'])
        self.assertEqual(c['dispatch_timestamps'], 7)  # 0,1,2,10,30,60,100
