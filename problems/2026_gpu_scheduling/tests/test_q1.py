"""Independent numerical checks of the Q1 window and distribution corrections."""
import unittest

import numpy as np

from gpu_scheduling.q1 import ccdf, demand_timeline, gini, interval_demand, lorenz, phase_exposure, top_share


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

    def test_binned_demand_crossing_boundaries_and_partial_day(self):
        # 2 GPUs [0,4), 3 GPUs [4,10), 5 GPUs [2,7); last arrival at T is excluded.
        bins, areas = interval_demand([0,4,2,10], [4,6,5,3], [2,3,5,99], 10, 4)
        self.assertEqual(bins.tolist(), [0,4,8,10])
        self.assertEqual(areas.tolist(), [18,27,6])
        self.assertEqual(int(areas.sum()), 51)

    def test_daily_integral_matches_independent_overlap_for_every_bin(self):
        arrival=np.array([0,86399,86400,172799,180000])
        duration=np.array([90000,2,86400,20000,1])
        quantity=np.array([2,3,5,7,999])
        bins,areas=interval_demand(arrival,duration,quantity,180000)
        expected=[sum(int(q)*max(0,min(int(a+p),int(right))-max(int(a),int(left)))
                      for a,p,q in zip(arrival,duration,quantity))
                  for left,right in zip(bins[:-1],bins[1:])]
        self.assertEqual(areas.tolist(),expected)
        self.assertEqual(bins[-1]-bins[-2],7200)
