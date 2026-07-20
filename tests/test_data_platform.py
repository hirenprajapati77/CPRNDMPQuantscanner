"""
NDMP OS v6.0 - Data Platform Unit Tests
"""

import pytest
import pandas as pd
from datetime import date, datetime
from ndmp_core.src.trading_calendar import NSETradingCalendar
from ndmp_core.src.symbol_master import SymbolMasterRegistry, SymbolMetadata
from ndmp_core.src.data_quality import DataQualityAuditor
from ndmp_core.src.exceptions import DataValidationError


def test_trading_calendar_holidays():
    cal = NSETradingCalendar()
    # Republic Day 2026-01-26 is a holiday
    assert cal.is_trading_day(date(2026, 1, 26)) is False
    # Regular Sunday is not a trading day
    assert cal.is_trading_day(date(2026, 1, 25)) is False
    # Regular Monday (e.g. 2026-01-19) is a trading day
    assert cal.is_trading_day(date(2026, 1, 19)) is True


def test_symbol_master_registry():
    registry = SymbolMasterRegistry()
    registry.register_symbol(
        SymbolMetadata(
            symbol="BEL",
            company_name="Bharat Electronics Ltd",
            sector="Capital Goods",
            industry="Defense",
            lot_size=2850,
            is_fo_eligible=True,
            isin="INE263A01024",
            listing_date="2000-01-01"
        )
    )
    assert registry.count() == 1
    sym = registry.get_symbol("BEL")
    assert sym is not None
    assert sym.lot_size == 2850
    assert sym.sector == "Capital Goods"


def test_data_quality_auditor_pass():
    auditor = DataQualityAuditor()
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=10, freq="15min"),
        "symbol": ["BEL"] * 10,
        "open": [100.0] * 10,
        "high": [105.0] * 10,
        "low": [99.0] * 10,
        "close": [103.0] * 10,
        "volume": [5000] * 10,
        "open_interest": [12000] * 10,
        "vwap": [102.5] * 10
    })
    expected_cols = ["timestamp", "symbol", "open", "high", "low", "close", "volume", "open_interest", "vwap"]
    report = auditor.audit_dataframe(df, "TEST_DS", expected_cols)
    assert report.status == "ACCEPTED"
    assert report.quality_score == 100.0
    assert report.completeness_percent == 100.0


def test_data_quality_auditor_reject_empty():
    auditor = DataQualityAuditor()
    df = pd.DataFrame()
    with pytest.raises(DataValidationError):
        auditor.audit_dataframe(df, "EMPTY_DS", ["timestamp"])
