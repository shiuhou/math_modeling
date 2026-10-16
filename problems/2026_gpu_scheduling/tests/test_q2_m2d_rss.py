"""History reclamation must retain the complete schema-2 proof protocol."""
import copy
import unittest

from test_q2_m2b import _fixed_then_flex_fixture, _nodes
from gpu_scheduling.validation import validate_reservations


class ReservationContextRelease(unittest.TestCase):
    def check_bad(self, mutate):
        jobs, result = _fixed_then_flex_fixture()
        mutate(result)
        with self.assertRaises((AssertionError, ValueError, TypeError)):
            validate_reservations(_nodes(), jobs, result)

    def test_fulfillment_requires_immediate_matching_unique_start(self):
        def missing(r):
            r['events'] = [e for e in r['events'] if not (e['kind'] == 'start' and e['job'] == 1)]
        def duplicate(r):
            i = next(i for i, e in enumerate(r['events']) if e['kind'] == 'start' and e['job'] == 1)
            r['events'].insert(i + 1, copy.deepcopy(r['events'][i]))
        def swapped(r):
            i = next(i for i, e in enumerate(r['events']) if e['kind'] == 'reservation_fulfilled')
            r['events'][i], r['events'][i + 1] = r['events'][i + 1], r['events'][i]
        def intervening(r):
            i = next(i for i, e in enumerate(r['events']) if e['kind'] == 'reservation_fulfilled')
            r['events'].insert(i + 1, {'time': 10, 'kind': 'timer'})
        for mutate in (missing, duplicate, swapped, intervening):
            with self.subTest(mutation=mutate.__name__):
                self.check_bad(mutate)

    def test_duplicate_fulfillment_and_post_fulfillment_certificate_rejected(self):
        def duplicate(r):
            i = next(i for i, e in enumerate(r['events']) if e['kind'] == 'reservation_fulfilled')
            r['events'].insert(i + 2, copy.deepcopy(r['events'][i]))
        def late(r):
            e = copy.deepcopy(next(e for e in r['events'] if e['kind'] == 'certificate_update'))
            e['time'] = 10
            i = next(i for i, e in enumerate(r['events']) if e['kind'] == 'reservation_fulfilled')
            r['events'].insert(i + 2, e)
        for mutate in (duplicate, late):
            self.check_bad(mutate)

    def test_missing_start_finish_and_forged_final_witness_rejected(self):
        def missing_start(r):
            r['events'] = [e for e in r['events'] if not (e['kind'] == 'start' and e['job'] == 2)]
        def missing_finish(r):
            r['events'] = [e for e in r['events'] if not (e['kind'] == 'finish' and e['job'] == 2)]
        def witness(r):
            # Still fits in the final future snapshot; violates certificate chain.
            r['reservations'][0]['placement_witness'] = [[0, 2]]
        for mutate in (missing_start, missing_finish, witness):
            self.check_bad(mutate)

    def test_fixed_policy_cannot_forge_flex_certificate(self):
        self.check_bad(lambda r: r.update(policy='SPT-URGENT-FIXED'))

    def test_dense_context_is_released_only_after_protected_start(self):
        jobs, result = _fixed_then_flex_fixture()
        samples = []
        validate_reservations(_nodes(), jobs, result,
                              progress=lambda phase, action, **counts: samples.append((action, counts)))
        self.assertEqual(samples[-1][1]['promises_completed'], 1)
        self.assertEqual(samples[-1][1]['live_dense_contexts'], 0)
        self.assertEqual(samples[-1][1]['live_dense_bytes'], 0)


if __name__ == '__main__':
    unittest.main()
