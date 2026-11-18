from __future__ import annotations

import unittest
from decimal import Decimal

from astraljet.domain.errors import ValidationError
from astraljet.lab.drawdown_brake import gate, observe, release, start

D = Decimal


def run(values, threshold='0.2', state=None):
    state = state or start(values[0])
    for day, equity in enumerate(values):
        state = observe(state, equity, threshold=threshold, when=f'dzień {day}')
    return state


class DrawdownBrakeTest(unittest.TestCase):
    def test_stays_open_below_threshold_and_tracks_the_peak(self):
        state = run([2500, 2600, 2400, 2700, 2200])  # największy spadek 18,5% od 2700
        self.assertFalse(state.tripped)
        self.assertEqual(D(2700), state.peak)

    def test_trips_exactly_at_threshold_and_records_when(self):
        state = run([2500, 2600, 2080])  # 2080 to dokładnie 20% poniżej 2600
        self.assertTrue(state.tripped)
        self.assertEqual('dzień 2', state.tripped_at)
        self.assertEqual(D(2080), state.tripped_equity)

    def test_does_not_resume_on_its_own_after_recovery(self):
        tripped = run([2500, 1900])
        later = run([2600, 3000, 5000], state=tripped)
        self.assertTrue(later.tripped)
        self.assertEqual(tripped, later)

    def test_gate_zeroes_targets_only_when_tripped(self):
        targets = {'SP500': 0.2, 'GOLD': 0.1}
        self.assertEqual(targets, gate(run([2500, 2400]), targets))
        self.assertEqual({'SP500': 0, 'GOLD': 0}, gate(run([2500, 1900]), targets))

    def test_release_needs_a_named_person_and_restarts_the_peak(self):
        tripped = run([2500, 1900])
        for nobody in ('', '   ', None):
            with self.assertRaises(ValidationError):
                release(tripped, 1900, by=nobody, when='2026-12-01')
        released = release(tripped, 1900, by=' Karol ', when='2026-12-01')
        self.assertFalse(released.tripped)
        self.assertEqual((D(1900), 'Karol', '2026-12-01'), (released.peak, released.released_by, released.released_at))
        self.assertFalse(run([1900, 1600], state=released).tripped)  # 15,8% od nowego szczytu
        self.assertTrue(run([1900, 1500], state=released).tripped)
        with self.assertRaises(ValidationError):
            release(released, 1900, by='Karol', when='2026-12-02')

    def test_account_at_or_below_zero_trips(self):
        self.assertTrue(run([2500, 0]).tripped)
        self.assertTrue(run([2500, -40]).tripped)

    def test_bad_numbers_are_refused(self):
        for equity in (float('nan'), float('inf'), None, 'abc'):
            with self.subTest(equity=equity), self.assertRaises(ValidationError):
                observe(start(2500), equity, threshold='0.2', when='x')
        for threshold in (0, -0.1, 1, 1.5, float('nan'), None):
            with self.subTest(threshold=threshold), self.assertRaises(ValidationError):
                observe(start(2500), 2400, threshold=threshold, when='x')
        for capital in (0, -1, float('nan')):
            with self.subTest(capital=capital), self.assertRaises(ValidationError):
                start(capital)


if __name__ == '__main__':
    unittest.main()
