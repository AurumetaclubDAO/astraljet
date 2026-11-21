# -*- coding: utf-8 -*-
"""Czas serwera Vantage -> UTC. ZAŁOŻENIE: serwer = UTC+3 w okresie DST w USA (NY close), inaczej UTC+2.
Zweryfikowane 14.11.2026: offset z żywego tiku ETHUSD = +2 h (zima)."""
import datetime as dt, numpy as np

def _us_dst_bounds_utc(year):
    mar = dt.date(year, 3, 1); first_sun_mar = mar + dt.timedelta(days=(6 - mar.weekday()) % 7)
    start = dt.datetime.combine(first_sun_mar + dt.timedelta(days=7), dt.time(7), tzinfo=dt.timezone.utc)
    nov = dt.date(year, 11, 1); first_sun_nov = nov + dt.timedelta(days=(6 - nov.weekday()) % 7)
    end = dt.datetime.combine(first_sun_nov, dt.time(6), tzinfo=dt.timezone.utc)
    return start.timestamp(), end.timestamp()

def server_offset_s(server_epoch_s):
    s = np.asarray(server_epoch_s, dtype="float64"); off = np.full(s.shape, 2 * 3600.0)
    for y in range(2020, 2031):
        a, b = _us_dst_bounds_utc(y)
        off[(s - 3 * 3600 >= a) & (s - 3 * 3600 < b)] = 3 * 3600.0
    return off

def to_utc_s(server_epoch_s):
    s = np.asarray(server_epoch_s, dtype="float64"); return s - server_offset_s(s)
