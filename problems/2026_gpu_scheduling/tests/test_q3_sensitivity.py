"""Small deterministic contracts for the predeclared Q3-S2 sensitivity study."""
from dataclasses import replace
import unittest

from gpu_scheduling.q3 import Config, TARGET, route, selected, simulate
from test_q3 import fixture


class Q3SensitivityContracts(unittest.TestCase):
    def test_hash_routing_is_nested(self):
        c5 = Config(route_numerator=1, route_denominator=20)
        c10 = replace(c5, route_denominator=10)
        c20 = replace(c5, route_denominator=5)
        for job_id in range(5000):
            self.assertFalse(selected(job_id, c5) and not selected(job_id, c10))
            self.assertFalse(selected(job_id, c10) and not selected(job_id, c20))

    def test_donor_prefixes_are_nested(self):
        nodes, _ = fixture()
        target = nodes[nodes.gpu_model == TARGET].sort_values('node_name')
        self.assertTrue(set(target.head(1).node_name) < set(target.head(2).node_name))

    def test_sigma_two_changes_duration_and_sjf_order(self):
        nodes, jobs = fixture()
        base = Config(donor_nodes=1, route_numerator=1, route_denominator=1, sigma=1, horizon_seconds=100)
        slow = replace(base, sigma=2)
        _, b = route(nodes, jobs, base)
        _, s = route(nodes, jobs, slow)
        routed = b.route_reason == 'routed'
        self.assertTrue((s.loc[routed, 'duration'] == 2 * b.loc[routed, 'original_duration']).all())
        self.assertTrue((s.loc[~routed, 'duration'] == b.loc[~routed, 'duration']).all())
        f1, _ = simulate(nodes, jobs, 'SJF-HOL', base)
        f2, _ = simulate(nodes, jobs, 'SJF-HOL', slow)
        self.assertTrue((f1.start.to_numpy() != f2.start.to_numpy()).any())


if __name__ == '__main__':
    unittest.main()
