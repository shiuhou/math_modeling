import unittest
import numpy as np
import pandas as pd

from gpu_scheduling.placement import plan_ratio_matching, plan_first_fit
from gpu_scheduling.simulator import simulate_pool


def _nodes(gpu, cpu):
    return pd.DataFrame({"node_name": list(range(len(gpu))), "gpu_model": ["X"] * len(gpu),
                         "gpu_capacity_num": gpu, "cpu_num": [x / 100 for x in cpu],
                         "cpu_units": cpu})


def _jobs(cpu, workers=1, q=1, duration=3, submit=None):
    n = len(cpu)
    return pd.DataFrame({"job_name": list(range(n)), "gpu_model": ["X"] * n,
                         "gpu_request": [q] * n, "cpu_units": cpu,
                         "worker_num": [workers] * n if isinstance(workers, int) else workers,
                         "submit_time": [0] * n if submit is None else submit,
                         "duration": [duration] * n})


class GangPlacementChecks(unittest.TestCase):
    def test_ratio_prefers_shape_and_keeps_fallback(self):
        fg = np.array([2, 2], dtype=np.int64)
        fc = np.array([100, 400], dtype=np.int64)
        p = plan_ratio_matching(fg, fc, 1, 300, 1, capacity_g=fg, capacity_c=fc)
        self.assertEqual(p.nodes, ((1, 1),))
        # The low-ratio node is still a legal fallback for a small worker.
        p2 = plan_ratio_matching(fg, fc, 1, 75, 3, capacity_g=fg, capacity_c=fc)
        self.assertEqual(p2.nodes, ((1, 2), (0, 1)))

    def test_zero_cpu_multigpu_atomic_and_tie(self):
        fg = np.array([2, 2], dtype=np.int64)
        fc = np.array([100, 100], dtype=np.int64)
        p = plan_ratio_matching(fg, fc, 2, 0, 2, capacity_g=fg, capacity_c=fc)
        self.assertEqual(p.nodes, ((0, 1), (1, 1)))
        self.assertEqual(plan_first_fit(fg, fc, 2, 0, 2).nodes, ((0, 1), (1, 1)))

    def test_ratio_and_ff_are_reproducible_with_explicit_order(self):
        nd = _nodes([1, 1], [100, 400])
        jj = _jobs([300, 100], workers=[1, 1], submit=[0, 1])
        a = simulate_pool(nd, jj, "FCFS-HOL", placement="ratio", node_order=[1, 0])
        b = simulate_pool(nd, jj, "FCFS-HOL", placement="ratio", node_order=[1, 0])
        self.assertEqual(a["starts"].tolist(), b["starts"].tolist())
        self.assertEqual(a["plans"], b["plans"])

    def test_default_ff_id_path_is_unchanged(self):
        nd = _nodes([1, 1], [400, 100])
        jj = _jobs([100, 300], workers=[1, 1], submit=[0, 0])
        old = simulate_pool(nd, jj, "FCFS-HOL")
        explicit = simulate_pool(nd, jj, "FCFS-HOL", placement="ff-id", node_order=[0, 1])
        self.assertEqual(old["starts"].tolist(), explicit["starts"].tolist())
        self.assertEqual(old["plans"], explicit["plans"])
