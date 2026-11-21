"""Rejestr prób: warianty serii 2 trafiają do tabeli i do łącznej liczby prób."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'research' / 'tools'))

import rejestr_prob as rp  # noqa: E402


def variant(label: str, scenario: str = 'base', delay: int = 0, params=(252, 60)) -> dict:
    return {'label': label, 'params': list(params), 'scenario': scenario, 'delay': delay,
            'out_of_sample': {'net_return': -0.05, 'max_drawdown': 0.1, 'sharpe': -0.2}}


class SeriesTwoRows(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name)
        saved = (rp.H1_FILE, rp.H23_FILE, rp.DIAG_FILE, rp.S2_FILE)
        self.addCleanup(lambda: setattr_all(saved))
        rp.H1_FILE = rp.H23_FILE = rp.DIAG_FILE = folder / 'brak.json'
        rp.S2_FILE = folder / 'wynik_seria2_2500.json'
        result = {'hypothesis': 'H4', 'verdict': 'FAIL', 'checks': [{'passed': True}] + [{'passed': False}] * 5,
                  'variants': [variant(f'główny_{s}_opóźnienie{d}', s, d) for s in ('base', 'stress') for d in (0, 1)],
                  'neighbours': [variant(f'sąsiad_{l}_{v}', params=(l, v)) for l, v in
                                 [(202, 48), (202, 60), (202, 72), (252, 48), (252, 72), (302, 48), (302, 60), (302, 72)]],
                  'benchmark': variant('punkt_odniesienia')}
        rp.S2_FILE.write_text(json.dumps({'generated_at': '2026-11-21T03:00:00+00:00', 'capital': 2500, 'gross': 1,
                                          'data_sha256': {'IWM': 'a' * 64, 'ETHUSD': 'b' * 64},
                                          'results': [result, {**result, 'hypothesis': 'H5'}]}), encoding='utf-8')

    def test_both_hypotheses_and_all_variants_are_counted(self):
        text = rp.build()
        self.assertIn('Uruchomionych wariantów łącznie: 24.', text)
        self.assertEqual(text.count('| H4 | '), 1 + 12)
        self.assertEqual(text.count('| H5 | '), 1 + 12)
        self.assertIn('| H4 | trend w obie strony, koszyk CFD w lotach | FAIL | 1 z 6 | 12 | 2026-11-21 |', text)

    def test_benchmark_is_not_counted_as_a_trial(self):
        self.assertNotIn('punkt_odniesienia', rp.build())


def setattr_all(saved) -> None:
    rp.H1_FILE, rp.H23_FILE, rp.DIAG_FILE, rp.S2_FILE = saved


if __name__ == '__main__':
    unittest.main()
