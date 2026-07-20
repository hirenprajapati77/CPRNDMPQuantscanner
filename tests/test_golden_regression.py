"""
NDMP OS v6.0 - Golden Regression Test Suite
Verifies deterministic rankings, scores, and signals against a frozen historical benchmark.
"""

import os
import pytest
import pandas as pd
from ndmp_core.src.scanner_engine import ScannerEngine
from ndmp_core.src.ranking_engine import RankingEngine
from ndmp_core.src.decision_journal import DecisionJournalLogger


def test_golden_regression_2025_07_18():
    """
    Golden Regression Test for Frozen Session 2025-07-18.
    Ensures zero unwanted deviation in rankings, scores, and reasons across future commits.
    """
    scanner = ScannerEngine()
    ranker = RankingEngine()

    dates = pd.date_range("2025-07-18 15:15:00", periods=5, freq="1min")

    # Stock 1: BEL - Strong Narrow CPR (high=200.0, low=199.5, width < 0.5%) + Long Build-up (Price Up, OI Up)
    df_bel = pd.DataFrame({
        "timestamp": dates,
        "symbol": ["BEL"] * 5,
        "open": [198.0, 198.5, 199.0, 199.2, 199.5],
        "high": [200.0] * 5,
        "low": [199.5] * 5,
        "close": [198.5, 199.0, 199.2, 199.5, 199.8],
        "volume": [10000] * 5,
        "open_interest": [50000, 51000, 52000, 53000, 54000],
        "vwap": [198.5] * 5,
        "benchmark_close": [24000.0] * 5
    })

    # Stock 2: TRENT - Wide CPR (high=5000, low=4500, width = 10%) + Long Build-up (Price Up, OI Up)
    df_trent = pd.DataFrame({
        "timestamp": dates,
        "symbol": ["TRENT"] * 5,
        "open": [4920.0, 4930.0, 4940.0, 4950.0, 4960.0],
        "high": [5000.0] * 5,
        "low": [4500.0] * 5,
        "close": [4930.0, 4940.0, 4950.0, 4960.0, 4970.0],
        "volume": [5000] * 5,
        "open_interest": [20000, 20500, 21000, 21500, 22000],
        "vwap": [4950.0] * 5,
        "benchmark_close": [24000.0] * 5
    })

    # Stock 3: DIXON - Short Build-up (Price Down, OI Up) + Below VWAP + Wide CPR (width = 8.4%)
    df_dixon = pd.DataFrame({
        "timestamp": dates,
        "symbol": ["DIXON"] * 5,
        "open": [11950.0, 11920.0, 11900.0, 11870.0, 11850.0],
        "high": [12500.0] * 5,
        "low": [11500.0] * 5,
        "close": [11920.0, 11900.0, 11870.0, 11850.0, 11820.0],
        "volume": [8000] * 5,
        "open_interest": [30000, 31000, 32000, 33000, 34000],
        "vwap": [11900.0] * 5,
        "benchmark_close": [24000.0] * 5
    })

    sig_bel = scanner.scan_symbol("BEL", df_bel)
    sig_trent = scanner.scan_symbol("TRENT", df_trent)
    sig_dixon = scanner.scan_symbol("DIXON", df_dixon)

    ranked_results = ranker.rank_candidates([sig_bel, sig_trent, sig_dixon])

    # Golden Regression Assertions
    assert len(ranked_results) == 3

    # Rank 1 must be BEL (Narrow CPR + Long Build-up + Above VWAP)
    top_1 = ranked_results[0]
    assert top_1.symbol == "BEL"
    assert top_1.rank == 1
    assert top_1.signals.is_narrow_cpr is True
    assert top_1.signals.buildup_code == 1  # Long Build-up
    assert "✔ Narrow CPR" in top_1.reasons[0]
    assert "✔ Long Build-up" in top_1.reasons[1]

    # Rank 2 must be TRENT (Wide CPR, but Long Build-up + Above VWAP)
    top_2 = ranked_results[1]
    assert top_2.symbol == "TRENT"
    assert top_2.rank == 2
    assert top_2.signals.is_narrow_cpr is False

    # Rank 3 must be DIXON (Short Build-up & Below VWAP)
    top_3 = ranked_results[2]
    assert top_3.symbol == "DIXON"
    assert top_3.rank == 3
    assert top_3.score == 35.0


def test_decision_journal_logger(tmp_path):
    scanner = ScannerEngine()
    ranker = RankingEngine()

    dates = pd.date_range("2025-07-18 15:15:00", periods=5, freq="1min")
    df_bel = pd.DataFrame({
        "timestamp": dates,
        "symbol": ["BEL"] * 5,
        "open": [198.0, 198.5, 199.0, 199.2, 199.5],
        "high": [200.0] * 5,
        "low": [199.5] * 5,
        "close": [198.5, 199.0, 199.2, 199.5, 199.8],
        "volume": [10000] * 5,
        "open_interest": [50000, 51000, 52000, 53000, 54000],
        "vwap": [198.5] * 5,
        "benchmark_close": [24000.0] * 5
    })

    sig_bel = scanner.scan_symbol("BEL", df_bel)
    ranked_results = ranker.rank_candidates([sig_bel])

    logger = DecisionJournalLogger(journal_dir=str(tmp_path))
    manifest_p, journal_p = logger.log_scan_session(ranked_candidates=ranked_results, runtime_ms=12.5)

    assert os.path.exists(manifest_p)
    assert os.path.exists(journal_p)


def test_scanner_empty_df_rejection():
    """Verify scanner engine rejects empty DataFrames with DataValidationError."""
    from ndmp_core.src.exceptions import DataValidationError
    scanner = ScannerEngine()
    df = pd.DataFrame()
    with pytest.raises(DataValidationError, match="input DataFrame is empty"):
        scanner.scan_symbol("BEL", df)


def test_scanner_nan_handling():
    """Verify scanner engine rejects inputs containing NaN values in key feature dependencies."""
    from ndmp_core.src.exceptions import DataValidationError
    import numpy as np
    scanner = ScannerEngine()
    dates = pd.date_range("2025-07-18 15:15:00", periods=5, freq="1min")
    df_nan = pd.DataFrame({
        "timestamp": dates,
        "symbol": ["BEL"] * 5,
        "open": [198.0, 198.5, 199.0, 199.2, 199.5],
        "high": [200.0] * 5,
        "low": [199.5] * 5,
        "close": [198.5, 199.0, 199.2, 199.5, np.nan],  # NaN Close will produce NaNs
        "volume": [10000] * 5,
        "open_interest": [50000] * 5,
        "vwap": [198.5] * 5,
        "benchmark_close": [24000.0] * 5
    })
    with pytest.raises(DataValidationError, match="NaN value detected in feature"):
        scanner.scan_symbol("BEL", df_nan)


def test_ranking_tie_breaking():
    """Verify that ranking engine breaks ties deterministically via alphabetical sorting of symbols."""
    from ndmp_core.src.scanner_engine import StockSignals
    ranker = RankingEngine()
    
    # Create two signals with identical score signatures
    sig_xyz = StockSignals(
        symbol="XYZ", timestamp="2025-07-18 15:23:00", is_narrow_cpr=True, cpr_width_pct=0.2,
        vwap_dist_pct=0.5, buildup_code=1, mansfield_rs=1.5, close=200.0, cam_h4=205.0, cam_l4=195.0
    )
    sig_abc = StockSignals(
        symbol="ABC", timestamp="2025-07-18 15:23:00", is_narrow_cpr=True, cpr_width_pct=0.2,
        vwap_dist_pct=0.5, buildup_code=1, mansfield_rs=1.5, close=200.0, cam_h4=205.0, cam_l4=195.0
    )


    ranked_1 = ranker.rank_candidates([sig_xyz, sig_abc])
    ranked_2 = ranker.rank_candidates([sig_abc, sig_xyz])

    # Irrespective of input order, ABC (alphabetically first) must be Rank 1
    assert ranked_1[0].symbol == "ABC"
    assert ranked_1[1].symbol == "XYZ"
    
    assert ranked_2[0].symbol == "ABC"
    assert ranked_2[1].symbol == "XYZ"

