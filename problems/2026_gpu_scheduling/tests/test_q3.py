"""Physical counterexamples and routing information-boundary tests for Q3."""
from dataclasses import replace
import unittest

import pandas as pd

from gpu_scheduling.data import prepare_data
from gpu_scheduling.q3 import Config, FOREIGN, TARGET, describe, route, selected, simulate
from gpu_scheduling.q3_validation import verify_schedule, verify_metrics
from gpu_scheduling.validation import reference_small


def fixture():
    nodes = pd.DataFrame([(1, 'A10', 1, 4), (2, 'A10', 1, 4),
                          (10, TARGET, 2, 4), (11, TARGET, 2, 4)],
                         columns=['node_name', 'gpu_model', 'gpu_capacity_num', 'cpu_num'])
    jobs = pd.DataFrame([(1, 'A10', 2, 1, 2, 0, 10),
                         (2, 'A10', 2, 1, 1, 0, 2),
                         (3, TARGET, 2, 1, 2, 0, 10),
                         (4, TARGET, 2, 1, 2, 1, 2),
                         (5, 'A10', 2, 1, 1, 10, 1)],
                        columns=['job_name', 'gpu_model', 'cpu_request', 'gpu_request',
                                 'worker_num', 'submit_time', 'duration'])
    return prepare_data(nodes, jobs)


class Q3Tests(unittest.TestCase):
    def setUp(self):
        self.nodes, self.jobs = fixture()
        self.cfg = Config(donor_nodes=1, route_numerator=1, route_denominator=1, horizon_seconds=10)

    def run_case(self, policy='FCFS', cfg=None):
        c = cfg or self.cfg
        f, ledger = simulate(self.nodes, self.jobs, policy, c)
        verify_schedule(self.nodes, self.jobs, f, ledger, c)
        verify_metrics(self.nodes, f, c, describe(self.nodes, f, c))
        return f.set_index('job_name'), ledger

    def test_hand_fcfs_queue_release_and_native_harm(self):
        f, _ = self.run_case()
        self.assertEqual(f.start.tolist(), [0, 10, 0, 10, 10])
        baseline, _ = self.run_case(cfg=replace(self.cfg, donor_nodes=0))
        self.assertEqual(baseline.loc[4, 'start'], 1)
        self.assertEqual(f.loc[4, 'start']-baseline.loc[4, 'start'], 9)
        # Selected job waits rather than falling back to idle A10.
        self.assertEqual(f.loc[2, 'partition'], FOREIGN)

    def test_sjf_hol_and_independent_scalar_oracle(self):
        pools, routed = route(self.nodes, self.jobs, self.cfg)
        for policy in ['FCFS', 'SJF-HOL']:
            f, _ = self.run_case(policy)
            for key, sub in routed.groupby('partition'):
                expected = reference_small(pools[key], sub, policy)
                ordered = sub.sort_values(['submit_time', 'job_name'])
                self.assertEqual(list(f.loc[ordered.job_name, 'start']), expected)
        f, _ = self.run_case('SJF-HOL')
        self.assertEqual(f.loc[2, 'start'], 0)
        self.assertEqual(f.loc[1, 'start'], 2)

    def test_cpu_bottleneck_same_node(self):
        self.jobs.loc[self.jobs.job_name == 1, 'worker_num'] = 1
        self.jobs.loc[self.jobs.job_name.isin([1, 2]), 'cpu_request'] = 4
        self.jobs.loc[self.jobs.job_name.isin([1, 2]), 'cpu_units'] = 400
        f, _ = self.run_case()
        self.assertEqual(f.loc[2, 'start'], 10)  # one GPU idle, CPU full

    def test_multinode_gang_structural_fallback(self):
        # One donor node cannot hold 3 workers, so the A10 job stays native.
        nodes = pd.concat([self.nodes, self.nodes.iloc[[0]].assign(node_name=3)])
        jobs = self.jobs.copy(); jobs.loc[jobs.job_name == 1, 'worker_num'] = 3
        f, ledger = simulate(nodes, jobs, 'FCFS', self.cfg)
        verify_schedule(nodes, jobs, f, ledger, self.cfg)
        self.assertEqual(f.set_index('job_name').loc[1, 'route_reason'], 'structurally_infeasible')
        self.assertEqual(set(ledger[ledger.job_name == 1].node_name), {1, 2, 3})

    def test_infeasible_native_partition_rejected(self):
        jobs = self.jobs.copy(); jobs.loc[jobs.job_name == 3, 'worker_num'] = 3
        with self.assertRaisesRegex(ValueError, 'infeasibility'):
            simulate(self.nodes, jobs, 'FCFS', self.cfg)

    def test_zero_and_disabled_exact_equivalence(self):
        a, al = simulate(self.nodes, self.jobs, 'FCFS', replace(self.cfg, donor_nodes=0))
        b, bl = simulate(self.nodes, self.jobs, 'FCFS', replace(self.cfg, compatibility=False))
        pd.testing.assert_frame_equal(a, b)
        pd.testing.assert_frame_equal(al, bl)

    def test_hash_no_future_or_order_dependence(self):
        c = replace(self.cfg, route_numerator=1, route_denominator=10)
        _, a = route(self.nodes, self.jobs, c)
        _, b = route(self.nodes, self.jobs.iloc[::-1], c)
        _, prefix = route(self.nodes, self.jobs[self.jobs.submit_time == 0], c)
        pd.testing.assert_series_equal(a.set_index('job_name').route_reason.sort_index(), b.set_index('job_name').route_reason.sort_index())
        pd.testing.assert_series_equal(a.set_index('job_name').loc[prefix.job_name, 'route_reason'], prefix.set_index('job_name').route_reason)
        self.assertEqual([selected(i, c) for i in [0, 1, 2, 3]], [False, False, False, False])

    def test_empty_foreign_queue_retains_idle_capacity(self):
        c = replace(self.cfg, route_numerator=0)
        f, ledger = simulate(self.nodes, self.jobs, 'FCFS', c)
        verify_schedule(self.nodes, self.jobs, f, ledger, c)
        report = describe(self.nodes, f, c)
        verify_metrics(self.nodes, f, c, report)
        self.assertEqual(report['physical'][FOREIGN]['gpu_allocation_rate_at_horizon'], 0)
        self.assertEqual(report['physical'][FOREIGN]['gpus'], 2)

    def test_bad_configuration_and_fractional_duration(self):
        for change in [dict(donor_nodes=-1), dict(sigma=0), dict(sigma=float('nan')), dict(route_denominator=0), dict(route_numerator=2, route_denominator=1), dict(donor_nodes=1.5)]:
            with self.assertRaises(ValueError):
                replace(self.cfg, **change)
        with self.assertRaisesRegex(ValueError, 'integer|int64'):
            simulate(self.nodes, self.jobs, 'FCFS', replace(self.cfg, sigma=.5))

    def test_corrupt_saved_job_identity_model_duration_and_time(self):
        f, ledger = simulate(self.nodes, self.jobs, 'FCFS', self.cfg)
        cases = [f.iloc[:-1], pd.concat([f, f.iloc[[0]]]),
                 f.assign(gpu_model='A10'), f.assign(duration=f.duration+1),
                 f.assign(start=f.start+.5)]
        for bad in cases:
            with self.subTest(case=len(bad)), self.assertRaises(AssertionError):
                verify_schedule(self.nodes, self.jobs, bad, ledger, self.cfg)

    def test_corrupt_ledger_duplicate_workers_partition(self):
        f, ledger = simulate(self.nodes, self.jobs, 'FCFS', self.cfg)
        for bad in [ledger.iloc[:-1], pd.concat([ledger, ledger.iloc[[0]]]),
                    ledger.assign(workers=ledger.workers*2), ledger.assign(node_name=11)]:
            with self.assertRaises(AssertionError):
                verify_schedule(self.nodes, self.jobs, f, bad, self.cfg)

    def test_capacity_overallocation_detected(self):
        f, ledger = simulate(self.nodes, self.jobs, 'FCFS', self.cfg)
        # Still valid durations, IDs, routing and placements; illegal simultaneous usage.
        mask = f.job_name == 2
        f.loc[mask, 'start'] = 0; f.loc[mask, 'finish'] = 2
        with self.assertRaisesRegex(AssertionError, 'capacity'):
            verify_schedule(self.nodes, self.jobs, f, ledger, self.cfg)

    def test_metrics_tamper_detected(self):
        f, _ = simulate(self.nodes, self.jobs, 'FCFS', self.cfg)
        report = describe(self.nodes, f, self.cfg)
        report['physical'][FOREIGN]['full_gpu_hours'] += 1
        with self.assertRaisesRegex(AssertionError, 'Metric mismatch'):
            verify_metrics(self.nodes, f, self.cfg, report)

class Q3PersistedCLI(unittest.TestCase):
    def test_roundtrip_and_semantic_tampering(self):
        import hashlib
        import json
        from pathlib import Path
        import subprocess
        import sys
        import tempfile
        problem = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(problem/'experiments'))
        from verify_q3_fixed_split import verify
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); data = base/'data'; data.mkdir()
            nodes, jobs = fixture()
            nodes.to_csv(data/'node_info_df.csv', index=False)
            jobs.to_csv(data/'job_info_clean.csv', index=False)
            config = base/'config.json'
            config.write_text(json.dumps(Config(donor_nodes=1, route_numerator=1, route_denominator=1, horizon_seconds=10).dictionary()))
            run = base/'run'
            command = [sys.executable, str(problem/'experiments/run_q3_fixed_split.py'),
                       '--data', str(data), '--config', str(config), '--out', str(run)]
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual(verify(data, run)['status'], 'PASS')
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            target = run/'FCFS_M1_placements.csv.gz'
            ledger = pd.read_csv(target); ledger.loc[0, 'workers'] += 1
            ledger.to_csv(target, index=False, compression='gzip')
            manifest = json.loads((run/'run.json').read_text())
            manifest['outputs'][target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
            (run/'run.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(AssertionError, 'Worker count'):
                verify(data, run)


if __name__ == '__main__':
    unittest.main()
