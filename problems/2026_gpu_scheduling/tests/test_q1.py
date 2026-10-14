"""Independent numerical checks of the Q1 window and distribution corrections."""
import unittest

import numpy as np

from gpu_scheduling.q1 import ccdf, demand_timeline, gini, lorenz, phase_exposure, top_share


class Q1Checks(unittest.TestCase):
    def test_seconds_integral_and_boundary_release(self):
        edges, values, area = demand_timeline([0, 2, 5], [2, 10, 1], [2, 3, 99], 5)
        self.assertEqual(area, 13)  # 2 GPUs * 2 s + 3 GPUs * 3 s.
        self.assertEqual(edges.tolist(), [0, 2, 5])
        self.assertEqual(values.tolist(), [2, 3])

    def test_gini_matches_pairwise_definition(self):
        values = np.array([1, 1, 2, 8])
        expected = np.abs(values[:, None]-values).sum()/(2*len(values)*values.sum())
        self.assertAlmostEqual(gini(values), expected)

    def test_lorenz_includes_origin_and_endpoint(self):
        x, y = lorenz([1, 1, 2])
        self.assertEqual((x[0], y[0]), (0, 0))
        self.assertEqual((x[-1], y[-1]), (1, 1))

    def test_ccdf_groups_tied_durations(self):
        x, probability = ccdf([1, 1, 2, 4])
        self.assertEqual(x.tolist(), [1, 2, 4])
        self.assertEqual(probability.tolist(), [.5, .25, 0])

    def test_top_count_is_floor(self):
        count, share = top_share([1, 2, 3], .5)
        self.assertEqual(count, 1)
        self.assertEqual(share, .5)

    def test_partial_phase_exposure(self):
        exposure = phase_exposure(86400+1800)
        self.assertEqual(exposure[0], 1.5)
        self.assertEqual(exposure[1], 1)
        self.assertEqual(exposure.sum()*3600, 86400+1800)
