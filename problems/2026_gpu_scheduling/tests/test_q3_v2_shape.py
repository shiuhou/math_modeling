"""Bounded R-shape routing and information-boundary checks."""
from dataclasses import replace
import unittest

import pandas as pd

from gpu_scheduling.data import prepare_data
from gpu_scheduling.q3 import Config, TARGET
from gpu_scheduling.q3_v2 import completion_cost_spec, derive_shape_limit, route_shape, shape_allowed, simulate_shape


def fixture():
    nodes = pd.DataFrame(
        [(1, "A10", 1, 128), (2, "A10", 1, 128), (10, TARGET, 8, 128), (11, TARGET, 8, 128)],
        columns=["node_name", "gpu_model", "gpu_capacity_num", "cpu_num"],
    )
    jobs = pd.DataFrame(
        [
            (1, "A10", 8, 1, 1, 0, 10),   # shape ratio 8: allowed
            (2, "A10", 20, 1, 1, 0, 2),  # shape ratio 20: rejected
            (3, "A10", 0, 1, 2, 0, 3),   # c=0, multi-worker: allowed
            (4, TARGET, 8, 1, 1, 0, 4),
        ],
        columns=["job_name", "gpu_model", "cpu_request", "gpu_request", "worker_num", "submit_time", "duration"],
    )
    return prepare_data(nodes, jobs)


class RShapeTests(unittest.TestCase):
    def setUp(self):
        self.nodes, self.jobs = fixture()
        self.cfg = Config(donor_nodes=1, route_numerator=1, route_denominator=1, horizon_seconds=20)

    def test_threshold_is_derived_from_donor_data(self):
        self.assertEqual(derive_shape_limit(self.nodes, 1), 16.0)
        self.assertTrue(shape_allowed(self.jobs.iloc[0], 16.0))
        self.assertFalse(shape_allowed(self.jobs.iloc[1], 16.0))

    def test_v1_eligibility_hash_then_shape_filter(self):
        _, routed = route_shape(self.nodes, self.jobs, self.cfg)
        by_id = routed.set_index("job_name")
        self.assertEqual(by_id.loc[1, "route_reason"], "routed")
        self.assertEqual(by_id.loc[2, "route_reason"], "shape_rejected")
        self.assertEqual(by_id.loc[3, "route_reason"], "routed")
        self.assertEqual(by_id.loc[2, "partition"], "A10")
        self.assertEqual(by_id.loc[2, "duration"], 2)

    def test_no_transfer_restores_isolated_schedule_and_keeps_partition(self):
        cfg = replace(self.cfg, route_numerator=0)
        _, routed = route_shape(self.nodes, self.jobs, cfg)
        self.assertTrue((routed.route_reason == "hash_unselected").sum() >= 1)
        self.assertTrue((routed.partition[routed.original_gpu_model == "A10"] == "A10").all())
        frame, _ = simulate_shape(self.nodes, self.jobs, "FCFS", cfg)
        self.assertEqual(set(frame.partition), {"A10", TARGET})

    def test_sigma_two_changes_only_routed_duration(self):
        one = route_shape(self.nodes, self.jobs, self.cfg)[1].set_index("job_name")
        two = route_shape(self.nodes, self.jobs, replace(self.cfg, sigma=2))[1].set_index("job_name")
        routed = one.route_reason == "routed"
        self.assertTrue((two.loc[routed, "duration"] == 2 * two.loc[routed, "original_duration"]).all())
        self.assertTrue((two.loc[~routed, "duration"] == two.loc[~routed, "original_duration"]).all())

    def test_reversing_arrival_order_does_not_change_route(self):
        _, a = route_shape(self.nodes, self.jobs, self.cfg)
        _, b = route_shape(self.nodes, self.jobs.iloc[::-1], self.cfg)
        pd.testing.assert_series_equal(a.set_index("job_name").route_reason.sort_index(), b.set_index("job_name").route_reason.sort_index())

    def test_completion_cost_is_explicitly_deferred_with_minimal_interface(self):
        spec = completion_cost_spec()
        self.assertEqual(spec["status"], "IMPLEMENTATION_DEFERRED")
        self.assertEqual(spec["eta_seconds"], 0)
        self.assertIn("route_on_arrival(state, job)", spec["minimum_interface"]["name"])


if __name__ == "__main__":
    unittest.main()
