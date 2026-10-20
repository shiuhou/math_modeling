"""Postprocessing only: no scheduler or routing implementation is imported."""
import importlib.util
import json
from pathlib import Path
import unittest

import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / 'experiments/analyze_q3_v2_tradeoffs.py'
spec = importlib.util.spec_from_file_location('tradeoffs', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def frame(finishes, ids=(1, 2, 3)):
    return pd.DataFrame({'finish': finishes, 'start': [0, 0, 0],
                         'submit_time': [0, 0, 0]}, index=pd.Index(ids, name='job_name'))


class TradeoffTests(unittest.TestCase):
    def test_pair_signed_mean_and_conditional_denominator(self):
        p = m.pair(frame([7200, 3600, 3600]), frame([3600, 7200, 0]))
        self.assertAlmostEqual(p['mean_finish_delta_hours'], 1 / 3)
        self.assertEqual(p['harmed_jobs'], 2)
        self.assertEqual(p['positive_finish_delay_job_hours'], 2)
        self.assertEqual(p['harmed_mean_finish_delta_hours'], 1)

    def test_reverse_does_not_negate_positive_total(self):
        a, b = frame([7200, 3600, 3600]), frame([3600, 7200, 0])
        p, q = m.pair(a, b), m.pair(b, a)
        self.assertAlmostEqual(p['mean_finish_delta_hours'], -q['mean_finish_delta_hours'])
        self.assertEqual(p['harmed_jobs'], q['improved_jobs'])
        self.assertEqual(q['positive_finish_delay_job_hours'], 1)
        self.assertEqual(p['positive_finish_delay_job_hours'], 2)

    def test_empty_harmed_group_is_null(self):
        p = m.pair(frame([1, 2, 3]), frame([1, 2, 3]))
        self.assertIsNone(p['harmed_mean_finish_delta_hours'])
        self.assertIsNone(p['harmed_p99_finish_delta_hours'])

    def test_missing_ids_rejected(self):
        with self.assertRaises(ValueError):
            m.pair(frame([1, 2, 3]), frame([1, 2, 3], (1, 2, 4)))

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):
            m.pair(frame([1, 2, 3], (1, 1, 3)), frame([1, 2, 3]))

    def test_missing_column_not_default_zero(self):
        with self.assertRaises((KeyError, ValueError)):
            m.pair(frame([1, 2, 3]).drop(columns='finish'), frame([1, 2, 3]))

    def test_nan_rejected(self):
        with self.assertRaises(ValueError):
            m.pair(frame([1, float('nan'), 3]), frame([1, 2, 3]))

    def test_reordering_pairs_by_id(self):
        a = frame([1, 2, 3])
        self.assertEqual(m.pair(a, a.iloc[::-1])['harmed_jobs'], 0)

    def test_discrete_worst_keeps_option_and_policy(self):
        rows = [{'policy': 'P', 'option': o, 'sigma': s, 'cohort': 'A10',
                 'mean_jct_hours': v} for o, s, v in
                [('M0', None, 10), ('R0', 1, 6), ('R0', 2, 12),
                 ('R-shape', 1, 8), ('R-shape', 2, 9)]]
        result = m.discrete_worst(rows)
        self.assertEqual([x['worst_mean_jct_hours'] for x in result], [10, 12, 9])
        self.assertEqual([x['best_of_three'] for x in result], [False, False, True])

    def test_discrete_missing_scenario_rejected(self):
        with self.assertRaises(ValueError):
            m.discrete_worst([{'policy': 'P', 'option': 'R0', 'sigma': 1,
                              'cohort': 'A10', 'mean_jct_hours': 6}])

    def test_discrete_duplicate_scenario_rejected(self):
        rows = [{'policy': 'P', 'option': o, 'sigma': s, 'cohort': 'A10',
                 'mean_jct_hours': v} for o, s, v in
                [('M0', None, 10), ('R0', 1, 6), ('R0', 2, 12),
                 ('R-shape', 1, 8), ('R-shape', 2, 9), ('R0', 1, 0)]]
        with self.assertRaises(ValueError):
            m.discrete_worst(rows)

    def test_wait_and_finish_harmed_denominators_are_distinct(self):
        a, b = frame([10800, 7200, 3600]), frame([3600, 3600, 3600])
        a['start'] = [3600, 0, 0]
        result = m.pair(a, b)
        self.assertEqual(result['harmed_jobs'], 2)
        self.assertEqual(result['wait_harmed_jobs'], 1)
        self.assertEqual(result['harmed_mean_finish_delta_hours'], 1.5)
        self.assertEqual(result['wait_harmed_mean_delta_hours'], 1)
        self.assertEqual(result['reference_zero_wait_newly_delayed'], 1)

    def test_committed_numeric_evidence_uses_fixed_groups(self):
        root = SCRIPT.parents[3] / 'results/20261018-b-q3-v2-r1-6f2c8a10'
        rows = json.loads((root / 'main_table.json').read_text())
        pairs = json.loads((root / 'paired.json').read_text())
        self.assertEqual(len(rows), 30)
        self.assertEqual(len(pairs), 66)
        by_key = {(r['policy'], r['option'], r['sigma'], r['cohort']): r for r in rows}
        for p in pairs:
            a = by_key[p['policy'], p['option'], p['sigma'], p['cohort']]
            b = by_key[p['policy'], p['reference'], p['reference_sigma'], p['cohort']]
            self.assertEqual(p['n'], {'A10': 111284, 'ALL': 224112, 'native_A100': 80877}[p['cohort']])
            self.assertAlmostEqual(p['mean_finish_delta_hours'], a['mean_jct_hours'] - b['mean_jct_hours'], places=9)
            if p['harmed_jobs']:
                self.assertAlmostEqual(p['harmed_mean_finish_delta_hours'], p['positive_finish_delay_job_hours'] / p['harmed_jobs'], places=9)
            else:
                self.assertIsNone(p['harmed_mean_finish_delta_hours'])
        for policy in ('FCFS', 'SJF-HOL'):
            self.assertGreater(by_key[policy, 'R-shape', 1, 'A10']['mean_jct_hours'], by_key[policy, 'R0', 1, 'A10']['mean_jct_hours'])
            self.assertLess(by_key[policy, 'R-shape', 2, 'A10']['mean_jct_hours'], by_key[policy, 'R0', 2, 'A10']['mean_jct_hours'])

    def test_published_route_work_conserves_original_work(self):
        root = SCRIPT.parents[3] / 'results/20261018-b-q3-v2-r1-6f2c8a10'
        audit = json.loads((root / 'routing.json').read_text())
        groups = audit['groups']
        self.assertEqual(audit['excluded_n'], 605)
        self.assertEqual(audit['r0_n'], audit['retained_n'] + audit['excluded_n'])
        for resource in ('gpu_work', 'cpu_work'):
            self.assertEqual(groups['R0'][resource]['original_seconds'],
                             groups['retained_Rshape'][resource]['original_seconds'] +
                             groups['excluded_R0_minus_Rshape'][resource]['original_seconds'])


if __name__ == '__main__':
    unittest.main()
