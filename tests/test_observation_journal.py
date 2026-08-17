import os
import shutil
import pytest
import pandas as pd
import numpy as np
from ndmp_core.src.observation_journal import ObservationJournal
from ndmp_core.src.ranking_engine import RankedCandidate, RankingEngine
from ndmp_core.src.scanner_engine import StockSignals

@pytest.fixture
def temp_journal_dir(tmp_path):
    d = tmp_path / "obs_journal"
    d.mkdir()
    yield str(d)

def create_mock_candidate(symbol: str, close: float, buildup_code: int, score: float) -> RankedCandidate:
    signals = StockSignals(
        symbol=symbol,
        timestamp="2026-08-04 15:30:00",
        is_narrow_cpr=True,
        cpr_width_pct=0.1,
        vwap_dist_pct=0.2,
        buildup_code=buildup_code,
        mansfield_rs=1.5,
        close=close,
        cam_h4=close + 1.0,
        cam_l4=close - 1.0
    )
    return RankedCandidate(
        rank=1,
        symbol=symbol,
        score=score,
        signals=signals,
        reasons=[]
    )

def test_score_split_long_buildup(temp_journal_dir):
    # Long buildup (code 1) should have positive contribution (+15)
    # So baseline_score should be less than full_score
    rc = create_mock_candidate("BEL", 100.0, 1, 95.0)
    journal = ObservationJournal(temp_journal_dir)
    journal.log_signals([rc], "2026-08-04")
    
    df = pd.read_parquet(journal._signals_path("BEL"))
    assert len(df) == 1
    assert df.iloc[0]["full_score"] == 95.0
    assert df.iloc[0]["baseline_score"] < 95.0

def test_score_split_short_covering(temp_journal_dir):
    # Short covering (code 2) should have positive contribution (+8)
    rc = create_mock_candidate("BEL", 100.0, 2, 88.0)
    journal = ObservationJournal(temp_journal_dir)
    journal.log_signals([rc], "2026-08-04")
    
    df = pd.read_parquet(journal._signals_path("BEL"))
    assert df.iloc[0]["baseline_score"] < 88.0

def test_score_split_short_buildup(temp_journal_dir):
    # Short buildup (code 3) should have negative penalty (-15)
    # So baseline_score should be greater than full_score
    rc = create_mock_candidate("BEL", 100.0, 3, 50.0)
    journal = ObservationJournal(temp_journal_dir)
    journal.log_signals([rc], "2026-08-04")
    
    df = pd.read_parquet(journal._signals_path("BEL"))
    assert df.iloc[0]["baseline_score"] > 50.0

def test_score_split_long_unwinding(temp_journal_dir):
    # Long unwinding (code 4) has 0 points in ranking engine logic
    rc = create_mock_candidate("BEL", 100.0, 4, 80.0)
    journal = ObservationJournal(temp_journal_dir)
    journal.log_signals([rc], "2026-08-04")
    
    df = pd.read_parquet(journal._signals_path("BEL"))
    assert df.iloc[0]["baseline_score"] == 80.0

def test_score_split_neutral(temp_journal_dir):
    # Neutral buildup (code 0) has 0 points
    rc = create_mock_candidate("BEL", 100.0, 0, 80.0)
    journal = ObservationJournal(temp_journal_dir)
    journal.log_signals([rc], "2026-08-04")
    
    df = pd.read_parquet(journal._signals_path("BEL"))
    assert df.iloc[0]["baseline_score"] == 80.0

def test_multi_day_append(temp_journal_dir):
    journal = ObservationJournal(temp_journal_dir)
    rc1 = create_mock_candidate("BEL", 100.0, 1, 95.0)
    rc2 = create_mock_candidate("BEL", 102.0, 2, 90.0)
    
    journal.log_signals([rc1], "2026-08-03")
    journal.log_signals([rc2], "2026-08-04")
    
    df = pd.read_parquet(journal._signals_path("BEL"))
    assert len(df) == 2
    assert df.iloc[0]["date"] == "2026-08-03"
    assert df.iloc[1]["date"] == "2026-08-04"

def test_outcome_resolution_idempotent(temp_journal_dir):
    journal = ObservationJournal(temp_journal_dir)
    rc = create_mock_candidate("BEL", 100.0, 1, 95.0)
    journal.log_signals([rc], "2026-08-03")
    
    # Mock OHLCV data
    ohlcv_df = pd.DataFrame({
        "timestamp": ["2026-08-03 15:30:00", "2026-08-04 15:30:00"],
        "open": [100.0, 101.5],
        "high": [105.0, 106.0],
        "low": [99.0, 100.0],
        "close": [100.0, 103.0]
    })
    
    # Resolve first time
    resolved_1 = journal.resolve_outcomes("BEL", ohlcv_df)
    assert len(resolved_1) == 1
    assert resolved_1.iloc[0]["next_day_close"] == 103.0
    assert resolved_1.iloc[0]["gap_pct"] == 1.5
    assert resolved_1.iloc[0]["next_day_return_pct"] == 3.0
    
    # Resolve second time (should be skipped due to idempotency)
    resolved_2 = journal.resolve_outcomes("BEL", ohlcv_df)
    assert resolved_2.empty

def test_incremental_resolution(temp_journal_dir):
    journal = ObservationJournal(temp_journal_dir)
    rc1 = create_mock_candidate("BEL", 100.0, 1, 95.0)
    rc2 = create_mock_candidate("BEL", 103.0, 2, 90.0)
    
    journal.log_signals([rc1], "2026-08-03")
    journal.log_signals([rc2], "2026-08-04")
    
    # OHLCV only containing up to August 4
    ohlcv_df_1 = pd.DataFrame({
        "timestamp": ["2026-08-03 15:30:00", "2026-08-04 15:30:00"],
        "open": [100.0, 101.5],
        "high": [105.0, 106.0],
        "low": [99.0, 100.0],
        "close": [100.0, 103.0]
    })
    
    # Resolves only August 3
    res1 = journal.resolve_outcomes("BEL", ohlcv_df_1)
    assert len(res1) == 1
    assert res1.iloc[0]["date"] == "2026-08-03"
    
    # OHLCV containing up to August 5
    ohlcv_df_2 = pd.DataFrame({
        "timestamp": ["2026-08-03 15:30:00", "2026-08-04 15:30:00", "2026-08-05 15:30:00"],
        "open": [100.0, 101.5, 104.0],
        "high": [105.0, 106.0, 107.0],
        "low": [99.0, 100.0, 103.0],
        "close": [100.0, 103.0, 105.0]
    })
    
    # Resolves August 4 incrementally
    res2 = journal.resolve_outcomes("BEL", ohlcv_df_2)
    assert len(res2) == 1
    assert res2.iloc[0]["date"] == "2026-08-04"
    assert res2.iloc[0]["next_day_close"] == 105.0

def test_missing_symbol_or_no_signals(temp_journal_dir):
    journal = ObservationJournal(temp_journal_dir)
    res = journal.resolve_outcomes("NONEXISTENT", pd.DataFrame())
    assert res.empty
