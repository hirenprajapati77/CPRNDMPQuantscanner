"""
NDMP OS v6.0 - Tests for NSETradingCalendar's market-hours boundary,
specifically the 15:40 IST derivatives close (extended from 15:30 following
NSE's Aug 3, 2026 CAS rollout, which left derivatives session hours untouched
but pushed them 10 minutes later).
"""

from datetime import datetime, date

from ndmp_core.src.trading_calendar import NSETradingCalendar


def _ist(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm)


def test_market_open_at_old_1530_boundary_still_true():
    """15:30 used to be the close — must still read as open now."""
    calendar = NSETradingCalendar(holidays=set())
    dt = _ist(2026, 8, 18, 15, 30)  # a Tuesday
    assert calendar.is_market_open(dt) is True


def test_market_open_at_new_1540_boundary_true():
    calendar = NSETradingCalendar(holidays=set())
    dt = _ist(2026, 8, 18, 15, 40)
    assert calendar.is_market_open(dt) is True


def test_market_closed_after_1540():
    calendar = NSETradingCalendar(holidays=set())
    dt = _ist(2026, 8, 18, 15, 41)
    assert calendar.is_market_open(dt) is False


def test_market_open_at_915_open_boundary():
    calendar = NSETradingCalendar(holidays=set())
    dt = _ist(2026, 8, 18, 9, 15)
    assert calendar.is_market_open(dt) is True


def test_market_closed_before_open():
    calendar = NSETradingCalendar(holidays=set())
    dt = _ist(2026, 8, 18, 9, 14)
    assert calendar.is_market_open(dt) is False


def test_market_closed_on_weekend_even_within_hours():
    calendar = NSETradingCalendar(holidays=set())
    saturday = _ist(2026, 8, 22, 15, 35)  # Aug 22 2026 is a Saturday
    assert calendar.is_market_open(saturday) is False
