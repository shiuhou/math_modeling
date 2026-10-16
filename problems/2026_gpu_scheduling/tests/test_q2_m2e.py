"""Equivalent current-placement memoization, including release invalidation."""
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from gpu_scheduling.placement import plan_first_fit
from gpu_scheduling.simulator import _CurrentPlacementCache, _priority, simulate_pool
from gpu_scheduling.validation import validate_reservations


class PlacementMemoization(unittest.TestCase):
    def test_demand_key_zero_cpu_and_invalidation(self):
        gpu, cpu = np.array([2, 1]), np.array([0, 100])
        cache = _CurrentPlacementCache(gpu, cpu)
        self.assertEqual(cache.get(1, 0, 2).nodes, ((0, 2),))
        self.assertIsNone(cache.get(1, 100, 2))
        self.assertIsNone(cache.get(1, 100, 2))
        self.assertEqual(cache.hits, 1)
        # An allocation invalidates a previously successful plan.
        gpu[0] = 0
        cache.invalidate()
        self.assertIsNone(cache.get(1, 0, 2))
        # A completion invalidates previously cached infeasibility.
        gpu[0], cpu[0] = 2, 200
        cache.invalidate()
        self.assertEqual(cache.get(1, 100, 2).nodes, ((0, 2),))

    def test_exact_uncached_equivalence_with_crossing_and_timers(self):
        # CPU shape makes FLEX crossing useful; subsequent arrivals exercise
        # both cached negative plans and cache invalidation on completion.
        nodes = pd.DataFrame({"node_name": [0, 1, 2], "gpu_model": ["X"] * 3,
                              "gpu_capacity_num": [2, 1, 1], "cpu_units": [100, 200, 200]})
        jobs = pd.DataFrame({"job_name": [0, 1, 2, 3, 4, 5], "gpu_model": ["X"] * 6,
                             "gpu_request": [1, 1, 2, 1, 1, 1],
                             "cpu_units": [200, 100, 0, 100, 100, 0],
                             "worker_num": [2, 2, 1, 2, 2, 1],
                             "submit_time": [0, 0, 1, 2, 3, 4],
                             "duration": [10, 10, 20, 2, 2, 3]})
        def uncached(cache, q, c, workers):
            return plan_first_fit(cache.free_g, cache.free_c, q, c, workers)
        def uncached_order(wait, policy, arr, dur, workers, reqg, priorities=None):
            return sorted(wait, key=lambda j: _priority(j, policy, arr, dur, workers, reqg))
        crossings = 0
        for mode in ("shared-timer", "arrival-completion-only"):
            for policy in ("FCFS-HOL", "SPT-HOL", "SGW-FILL", "SPT-FILL",
                           "SPT-URGENT-HOL", "SPT-URGENT-TIME", "SPT-URGENT-FIXED",
                           "SPT-URGENT-FLEX", "EASY-NR"):
                with self.subTest(mode=mode, policy=policy):
                    args = dict(theta_seconds=0, reservation_k=2, event_mode=mode)
                    actual = simulate_pool(nodes, jobs, policy, **args)
                    with patch.object(_CurrentPlacementCache, "get", uncached), \
                         patch("gpu_scheduling.simulator._ordered", uncached_order):
                        expected = simulate_pool(nodes, jobs, policy, **args)
                    for key in ("starts", "ends"):
                        np.testing.assert_array_equal(actual[key], expected[key])
                    for key in ("plans", "events", "reservations", "feasibility_checks"):
                        self.assertEqual(actual[key], expected[key])
                    validate_reservations(nodes, actual["jobs"], actual)
                    crossings += actual["cost"]["crossing_accepted"]
        self.assertGreater(crossings, 0)


if __name__ == "__main__":
    unittest.main()
