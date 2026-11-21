from __future__ import annotations

import unittest
from datetime import date, datetime

from astraljet.domain.errors import ValidationError
from astraljet.lab.data_freshness import check_freshness, require_fresh

MONDAY = '2026-11-23'


class DataFreshnessTest(unittest.TestCase):
    def test_friday_bar_is_fresh_on_monday_within_limit(self):
        report = check_freshness({'SPY': '2026-11-20'}, today=MONDAY, max_age_days=4)
        item = report['SPY']
        self.assertTrue(item.fresh)
        self.assertEqual((date(2026, 11, 20), 3, 4, ''), (item.last_bar, item.age_days, item.limit_days, item.reason))

    def test_bar_older_than_limit_is_stale_with_reason(self):
        item = check_freshness({'SPY': '2026-11-17'}, today=MONDAY, max_age_days=4)['SPY']
        self.assertFalse(item.fresh)
        self.assertEqual(6, item.age_days)
        self.assertIn('6 dni, limit to 4', item.reason)

    def test_age_equal_to_limit_is_still_fresh(self):
        self.assertTrue(check_freshness({'SPY': '2026-11-19'}, today=MONDAY, max_age_days=4)['SPY'].fresh)

    def test_bar_from_decision_day_or_later_is_refused_as_possibly_open(self):
        for last in (MONDAY, '2026-11-24'):
            item = check_freshness({'BTCUSD': last}, today=MONDAY, max_age_days=2)['BTCUSD']
            self.assertFalse(item.fresh, last)
            self.assertIn('mogła się jeszcze nie zamknąć', item.reason)

    def test_missing_data_is_stale(self):
        item = check_freshness({'TLT': None}, today=MONDAY, max_age_days=4)['TLT']
        self.assertEqual((False, None, None, 'brak danych'), (item.fresh, item.last_bar, item.age_days, item.reason))

    def test_limits_per_market(self):
        bars = {'BTCUSD': '2026-11-20', 'SPY': '2026-11-20'}
        report = check_freshness(bars, today=MONDAY, max_age_days={'BTCUSD': 1, 'SPY': 4})
        self.assertFalse(report['BTCUSD'].fresh)  # krypto handluje w weekend, piątkowa świeca w poniedziałek jest stara
        self.assertTrue(report['SPY'].fresh)

    def test_accepts_date_objects(self):
        report = check_freshness({'SPY': date(2026, 11, 20)}, today=date(2026, 11, 23), max_age_days=4)
        self.assertTrue(report['SPY'].fresh)

    def test_require_fresh_returns_report_when_all_fresh(self):
        report = require_fresh({'SPY': '2026-11-20', 'BTCUSD': '2026-11-22'}, today=MONDAY, max_age_days=4)
        self.assertEqual({'SPY', 'BTCUSD'}, set(report))

    def test_require_fresh_refuses_and_names_every_stale_market(self):
        bars = {'SPY': '2026-11-20', 'TLT': None, 'GLD': '2026-11-10'}
        with self.assertRaises(ValidationError) as caught:
            require_fresh(bars, today=MONDAY, max_age_days=4)
        message = caught.exception.message
        self.assertIn('TLT: brak danych', message)
        self.assertIn('GLD: ostatnia świeca z 2026-11-10 ma 13 dni', message)
        self.assertNotIn('SPY', message)
        self.assertEqual('nieświeże dane dzienne', caught.exception.blocker)

    def test_bad_inputs_are_refused(self):
        good = {'SPY': '2026-11-20'}
        cases = [
            (dict(last_bars={}, today=MONDAY, max_age_days=4), 'Brak rynków'),
            (dict(last_bars=good, today='23.11.2026', max_age_days=4), 'dzień decyzji'),
            (dict(last_bars=good, today=datetime(2026, 11, 23, 9, 0), max_age_days=4), 'dzień decyzji'),
            (dict(last_bars=good, today='2026-02-30', max_age_days=4), 'dzień decyzji'),
            (dict(last_bars={'SPY': 20261120}, today=MONDAY, max_age_days=4), 'SPY, ostatnia świeca'),
            (dict(last_bars=good, today=MONDAY, max_age_days=0), 'limit wieku danych'),
            (dict(last_bars=good, today=MONDAY, max_age_days=True), 'limit wieku danych'),
            (dict(last_bars=good, today=MONDAY, max_age_days=2.5), 'limit wieku danych'),
            (dict(last_bars=good, today=MONDAY, max_age_days={'QQQ': 4}), 'SPY: brak limitu'),
        ]
        for kwargs, expected in cases:
            with self.assertRaises(ValidationError, msg=expected) as caught:
                check_freshness(**kwargs)
            self.assertIn(expected, caught.exception.message)


if __name__ == '__main__':
    unittest.main()
