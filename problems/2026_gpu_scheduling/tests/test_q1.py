"""Independent numerical checks of the Q1 window and distribution corrections."""
import unittest
from fractions import Fraction
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np

from gpu_scheduling.q1 import MODEL_ORDER, capacity_bound, ccdf, demand_timeline, exact_record, gini, interval_demand, load_data, lorenz, phase_exposure, top_share


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


class CapacityBoundChecks(unittest.TestCase):
    def test_empty_zero_work_and_under_capacity(self):
        for a, d, g in [([], [], []), ([0], [0], [9]), ([0, 1], [2, 2], [1, 1])]:
            result = capacity_bound(a, d, g, 2)
            self.assertEqual(result['full_area_gpu_seconds_squared'], 0)
            self.assertEqual(result['lower_bound_seconds'], 0)

    def test_tail_is_half_of_hand_calculated_area(self):
        result = capacity_bound([0, 0], [1, 1], [1, 1], 1)
        self.assertEqual(result['area_before_last_finish_gpu_seconds_squared'], Fraction(1, 2))
        self.assertEqual(result['tail_area_gpu_seconds_squared'], Fraction(1, 2))
        self.assertEqual(result['full_area_gpu_seconds_squared'], 1)
        self.assertEqual(result['fluid_empty_seconds'], 2)
        self.assertEqual(result['total_gpu_seconds'], 2)
        self.assertEqual(result['lower_bound_seconds'], Fraction(1, 2))

    def test_interior_drain_triangle(self):
        result = capacity_bound([0, 3], [1, 1], [3, 1], 2)
        self.assertEqual(result['area_before_last_finish_gpu_seconds_squared'], Fraction(3, 4))
        self.assertEqual(result['tail_area_gpu_seconds_squared'], 0)
        self.assertEqual(result['lower_bound_seconds'], Fraction(3, 16))

    def test_coincident_events_origin_and_row_order(self):
        result = capacity_bound([0, 0, 1], [1, 1, 1], [1, 1, 1], 1)
        reverse = capacity_bound([1, 0, 0], [1, 1, 1], [1, 1, 1], 1)
        self.assertEqual(result, reverse)
        self.assertEqual(result['full_area_gpu_seconds_squared'], 2)
        self.assertEqual(result['lower_bound_seconds'], Fraction(2, 3))

    def test_sample_path_identity_independent_legal_schedule(self):
        # Independently evaluate cumulative ramps on their joint breakpoints.
        # Single GPU: jobs execute [0,2), [2,3), [3,4), legally nonpreemptive.
        arrival, duration, quantity, starts = [0, 0, 1], [2, 1, 1], [1, 1, 1], [0, 2, 3]
        edges = sorted({0, *arrival, *starts,
                        *(r+d for r, d in zip(arrival, duration)),
                        *(s+d for s, d in zip(starts, duration))})
        def deficit(t):
            return sum(g*(max(0, min(t-r, d))-max(0, min(t-s, d)))
                       for r, s, d, g in zip(arrival, starts, duration, quantity))
        integral = sum(Fraction((deficit(l)+deficit(r))*(r-l), 2)
                       for l, r in zip(edges, edges[1:]))
        weighted = sum(g*d*(s-r) for r, s, d, g in zip(arrival, starts, duration, quantity))
        self.assertEqual(integral, 4)
        self.assertEqual(integral, weighted)
        bound = capacity_bound(arrival, duration, quantity, 1)
        self.assertGreaterEqual(integral, bound['full_area_gpu_seconds_squared'])
        self.assertGreaterEqual(Fraction(weighted, sum(g*d for g, d in zip(quantity, duration))),
                                bound['lower_bound_seconds'])

    def test_arbitrary_precision_and_small_positive_display(self):
        big = 2**70
        result = capacity_bound([0], [big], [big], 1)
        self.assertEqual(result['total_gpu_seconds'], big**2)
        self.assertEqual(result['full_area_gpu_seconds_squared'], Fraction(big**3*(big-1), 2))
        self.assertEqual(result['lower_bound_seconds'], Fraction(big*(big-1), 2))
        tiny = exact_record(Fraction(1, 10**30))
        self.assertEqual(tiny['numerator'], 1)
        self.assertEqual(tiny['denominator'], 10**30)
        self.assertGreater(tiny['approximate'], 0)

    def test_invalid_inputs_rejected(self):
        for args in [([0], [1], [1], 0), ([0], [], [1], 1), ([-1], [1], [1], 1)]:
            with self.assertRaises(ValueError):
                capacity_bound(*args)
        with self.assertRaises(TypeError):
            capacity_bound([0.5], [1], [1], 1)

    def test_raw_six_pools_independent_prefix_minimum_integral(self):
        # Test-only oracle: X=F0-Ct and its running minimum, not a scheduler.
        # Reuse the old event timeline (safe for these raw magnitudes) but
        # independently integrate the lower-envelope deficit in Decimal.
        nodes, jobs, _ = load_data(Path(__file__).resolve().parents[1]/'data/raw')
        with localcontext() as context:
            context.prec = 80
            for model in MODEL_ORDER:
                j = jobs[jobs.gpu_model == model]
                capacity = sum(map(int, nodes.loc[nodes.gpu_model == model, 'gpu_capacity_num']))
                end = max(int(r)+int(d) for r, d in zip(j.submit_time, j.duration))
                edges, demand, work = demand_timeline(j.submit_time, j.duration, j.total_gpu, end)
                cumulative = minimum = Decimal(0)
                area = Decimal(0)
                for left, right, q in zip(edges[:-1], edges[1:], demand):
                    dt = Decimal(int(right)-int(left))
                    slope = Decimal(int(q)-capacity)
                    height = cumulative-minimum
                    active = min(dt, height/(-slope)) if slope < 0 else dt
                    area += height*active+slope*active*active/2
                    cumulative += slope*dt
                    minimum = min(minimum, cumulative)
                residual = cumulative-minimum
                total = area+residual*residual/(2*capacity)
                calculated = capacity_bound(j.submit_time, j.duration, j.total_gpu, capacity)
                rational = calculated['full_area_gpu_seconds_squared']
                expected = Decimal(rational.numerator)/Decimal(rational.denominator)
                with self.subTest(pool=model):
                    self.assertEqual(calculated['total_gpu_seconds'], work)
                    self.assertEqual(calculated['backlog_at_last_finish_gpu_seconds'], residual)
                    self.assertLess(abs(total-expected), Decimal('1e-50'))
