"""
NDMP OS v6.0 - NSE Trading Calendar & Market Session Engine
Handles NSE trading holidays, weekends, trading hours, and special sessions.

MARKET_CLOSE_TIME governs F&O/derivatives session hours (this project polls
futures OI, not cash-equity quotes). NSE's Closing Auction Session (CAS),
live since August 3, 2026 per SEBI circular HO/47/11/11(3)2025-MRD-POD2/I/
2765/2026, replaced the cash-equity closing-price mechanism for F&O-eligible
stocks (continuous cash trading now stops at 15:15, official close via
auction ~15:35) — but explicitly EXTENDED derivatives trading (stock/index
futures & options) by 10 minutes, to 15:40. Confirmed against two weeks of
real Angel One poller data (Aug 11-14): OI moves smoothly and continuously
through the old 15:30 boundary with no freeze/discontinuity, consistent with
the derivatives segment being unaffected by the cash-side auction mechanism.
If NSE further changes derivatives session hours, update MARKET_CLOSE_TIME
here — this is the single source of truth consumed by both OI pollers.
"""

import pandas as pd
from datetime import datetime, date, time
from typing import List, Set


class NSETradingCalendar:
    """NSE India Trading Calendar Manager."""
    
    # Official NSE Trading Holidays (Sample list, configurable)
    DEFAULT_HOLIDAYS_2026: Set[date] = {
        date(2026, 1, 26),  # Republic Day
        date(2026, 3, 25),  # Holi
        date(2026, 4, 14),  # Ambedkar Jayanti
        date(2026, 5, 1),   # Maharashtra Day
        date(2026, 8, 15),  # Independence Day
        date(2026, 10, 2),  # Gandhi Jayanti
        date(2026, 11, 1),  # Diwali Laxmi Pujan (Muhurat trading handled separately)
        date(2026, 12, 25), # Christmas
    }

    MARKET_OPEN_TIME: time = time(9, 15)
    MARKET_CLOSE_TIME: time = time(15, 40)
    SCANNER_TIME: time = time(15, 23)

    def __init__(self, holidays: Set[date] | None = None):
        self.holidays = holidays if holidays is not None else self.DEFAULT_HOLIDAYS_2026

    def is_trading_day(self, check_date: date) -> bool:
        """Check if a given date is a valid NSE trading day (weekday and non-holiday)."""
        if check_date.weekday() >= 5:  # Saturday or Sunday
            return False
        if check_date in self.holidays:
            return False
        return True

    def get_trading_days(self, start_date: date, end_date: date) -> List[date]:
        """Generate a list of all valid trading days between start_date and end_date inclusive."""
        all_days = pd.date_range(start=start_date, end=end_date, freq="D")
        return [d.date() for d in all_days if self.is_trading_day(d.date())]

    def is_market_open(self, dt: datetime) -> bool:
        """Check if a given timestamp falls within active trading hours."""
        if not self.is_trading_day(dt.date()):
            return False
        return self.MARKET_OPEN_TIME <= dt.time() <= self.MARKET_CLOSE_TIME
