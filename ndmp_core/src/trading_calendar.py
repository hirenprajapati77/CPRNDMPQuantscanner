"""
NDMP OS v6.0 - NSE Trading Calendar & Market Session Engine
Handles NSE trading holidays, weekends, trading hours (09:15-15:30 IST), and special sessions.
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
    MARKET_CLOSE_TIME: time = time(15, 30)
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
