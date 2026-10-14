"""Regressions for intake changes, not full-trace research validation."""
import unittest

import numpy as np
import pandas as pd

from gpu_scheduling.data import integer_array, prepare_data
from gpu_scheduling.evaluation import metrics
from gpu_scheduling.simulator import simulate_pool
from gpu_scheduling.validation import validate


class IntakeContracts(unittest.TestCase):
    def fixture(self):
        nodes = pd.DataFrame(dict(node_name=[0], gpu_model=["X"], gpu_capacity_num=[1], cpu_num=[.6]))
        jobs = pd.DataFrame(dict(job_name=[0], gpu_model=["X"], gpu_request=[1], cpu_request=[.6],
                                 worker_num=[1], submit_time=[0], duration=[2]))
        return nodes, jobs

    def test_fractional_capacity_and_raw_frame_preservation(self):
        raw_nodes, raw_jobs = self.fixture()
        nodes, jobs = prepare_data(raw_nodes, raw_jobs)
        self.assertNotIn("cpu_units", raw_nodes)
        self.assertNotIn("cpu_units", raw_jobs)
        self.assertEqual(nodes.cpu_units.tolist(), [60])
        self.assertEqual(simulate_pool(nodes, jobs, "FCFS")["starts"].tolist(), [0])

    def test_precision_rejected_without_rounding(self):
        with self.assertRaises(ValueError):
            integer_array(pd.Series([.001], name="cpu_request"), 100)

    def test_infeasible_job_is_reported_instead_of_default_zero_times(self):
        nodes, jobs = self.fixture()
        jobs["cpu_request"] = 2
        nodes, jobs = prepare_data(nodes, jobs)
        with self.assertRaisesRegex(ValueError, "infeasible"):
            simulate_pool(nodes, jobs, "FCFS")

    def test_models_cannot_share_a_pool(self):
        nodes, jobs = self.fixture()
        nodes, jobs = prepare_data(nodes, jobs)
        jobs["gpu_model"] = "Y"
        with self.assertRaisesRegex(ValueError, "matching GPU"):
            simulate_pool(nodes, jobs, "FCFS")

    def test_replay_rejects_overallocation_and_invalid_node_index(self):
        nodes, jobs = self.fixture()
        nodes, jobs = prepare_data(nodes, jobs)
        jobs["worker_num"] = 2
        with self.assertRaisesRegex(AssertionError, "capacity replay"):
            validate(nodes, jobs, np.array([0]), np.array([2]), [[(0, 2)]])
        jobs["worker_num"] = 1
        with self.assertRaisesRegex(AssertionError, "Placement contract"):
            validate(nodes, jobs, np.array([0]), np.array([2]), [[(-1, 1)]])

    def test_evaluator_does_not_claim_capacity_validation(self):
        nodes, jobs = self.fixture()
        nodes, jobs = prepare_data(nodes, jobs)
        values = metrics(dict(jobs=jobs, starts=np.array([0]), ends=np.array([2])), nodes, 1)
        self.assertEqual(values["mean_bounded_slowdown_60s"], 1)
        self.assertEqual(values["gpu_allocation_rate_at_horizon"], 1)
        self.assertNotIn("invariant_validation", values)
        with self.assertRaises(ValueError):
            metrics(dict(jobs=jobs, starts=np.array([-1]), ends=np.array([1])), nodes, 1)
