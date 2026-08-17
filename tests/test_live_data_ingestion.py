import pandas as pd
import numpy as np
import datetime
from fetch_live_data import merge_open_interest

def test_merge_open_interest_alignment():
    # 1. Mock stock dataframe from Yahoo Finance (June 1st to August 4th, date-only timestamps)
    stock_df = pd.DataFrame({
        "timestamp": [
            "2026-07-27 00:00:00",
            "2026-07-28 00:00:00",
            "2026-07-29 00:00:00",
            "2026-07-30 00:00:00",
            "2026-07-31 00:00:00",
            "2026-08-03 00:00:00",
            "2026-08-04 00:00:00"
        ],
        "close": [100.0, 102.0, 105.0, 104.0, 106.0, 108.0, 110.0]
    })
    
    # 2. Mock Angel One poller data (UTC timestamps)
    # Market close is 15:30 IST, which is 10:00 UTC.
    # Close window 15:15 - 15:30 IST is 09:45 - 10:00 UTC.
    oi_df = pd.DataFrame({
        "timestamp": [
            # July 28: manual snapshot at 12:07 IST (06:37 UTC) -> Should be ignored as it's outside 15:15-15:30 IST
            "2026-07-28 06:37:39.083286+00:00",
            
            # July 29: valid EOD close at 15:29 IST (09:59 UTC) -> Should be included
            "2026-07-29 09:59:42.375774+00:00",
            
            # July 30: mid-day snapshot (should be overridden by the later close snapshot)
            "2026-07-30 07:00:00.000000+00:00",
            # July 30: valid EOD close
            "2026-07-30 09:59:52.125699+00:00",
            
            # July 31: valid EOD close
            "2026-07-31 09:59:31.765701+00:00",
            
            # Aug 3: valid EOD close
            "2026-08-03 09:59:38.875291+00:00"
            
            # Aug 4 (today): currently mid-day (no snapshot in 15:15-15:30 window yet) -> Should not map today
        ],
        "open_interest": [
            88542375,  # July 28 (ignored)
            101421525, # July 29 (EOD)
            101200000, # July 30 (mid-day, ignored)
            101351700, # July 30 (EOD)
            103301100, # July 31 (EOD)
            103336725  # Aug 3 (EOD)
        ]
    })
    
    result = merge_open_interest(stock_df, oi_df)
    
    # Assertions
    # July 27: before data collection started -> np.nan (no look-ahead bfill!)
    assert np.isnan(result.iloc[0]["open_interest"])
    
    # July 28: manual snapshot is ignored -> np.nan
    assert np.isnan(result.iloc[1]["open_interest"])
    
    # July 29: EOD close mapped correctly
    assert result.iloc[2]["open_interest"] == 101421525
    
    # July 30: EOD close mapped correctly, overriding mid-day
    assert result.iloc[3]["open_interest"] == 101351700
    
    # July 31: EOD close mapped correctly
    assert result.iloc[4]["open_interest"] == 103301100
    
    # Aug 3: EOD close mapped correctly
    assert result.iloc[5]["open_interest"] == 103336725
    
    # Aug 4: no EOD snapshot yet -> np.nan (no ffill!)
    assert np.isnan(result.iloc[6]["open_interest"])


def test_merge_open_interest_late_recovery_and_deduplication():
    # Mock stock dataframe
    stock_df = pd.DataFrame({
        "timestamp": [
            "2026-08-05 00:00:00",
            "2026-08-06 00:00:00"
        ],
        "close": [100.0, 105.0]
    })
    
    # Mock Angel One poller data
    # 2026-08-05: has two snapshots >= 15:15 IST:
    #   - 15:20 IST (09:50 UTC): open interest 10000
    #   - 18:48 IST (13:18 UTC): open interest 12000 (late recovery poll, should override the 15:20 one)
    # 2026-08-06: has a single late recovery poll:
    #   - 19:30 IST (14:00 UTC): open interest 15000 (should be mapped successfully)
    oi_df = pd.DataFrame({
        "timestamp": [
            "2026-08-05 09:50:00+00:00",  # 2026-08-05 15:20 IST
            "2026-08-05 13:18:00+00:00",  # 2026-08-05 18:48 IST (EOD Recovery)
            "2026-08-06 14:00:00+00:00"   # 2026-08-06 19:30 IST (EOD Recovery)
        ],
        "open_interest": [
            10000,
            12000,
            15000
        ]
    })
    
    result = merge_open_interest(stock_df, oi_df)
    
    # 2026-08-05: Should resolve to the last EOD snapshot (12000)
    assert result.iloc[0]["open_interest"] == 12000
    
    # 2026-08-06: Late snapshot mapped correctly (15000)
    assert result.iloc[1]["open_interest"] == 15000


def test_resolve_active_oi_file(tmp_path):
    import os
    from fetch_live_data import resolve_active_oi_file
    
    d = tmp_path / "oi_history_angelone"
    d.mkdir()
    (d / "BEL25AUG26FUT.parquet").write_text("dummy")
    (d / "BEL24SEP26FUT.parquet").write_text("dummy")
    (d / "TRENT25AUG26FUT.parquet").write_text("dummy")
    (d / "BEL25AUG26FUT.txt").write_text("dummy")
    
    # 1. On August 10th (before August expiry) -> Should pick August contract
    res1 = resolve_active_oi_file("BEL", data_dir=str(d), current_date=datetime.date(2026, 8, 10))
    assert os.path.basename(res1) == "BEL25AUG26FUT.parquet"
    
    # 2. On August 25th (exact expiry day) -> Should still pick August contract
    res2 = resolve_active_oi_file("BEL", data_dir=str(d), current_date=datetime.date(2026, 8, 25))
    assert os.path.basename(res2) == "BEL25AUG26FUT.parquet"
    
    # 3. On August 26th (after August expiry) -> Should pick September contract
    res3 = resolve_active_oi_file("BEL", data_dir=str(d), current_date=datetime.date(2026, 8, 26))
    assert os.path.basename(res3) == "BEL24SEP26FUT.parquet"
    
    # 4. On October 1st (all expiries in the past) -> Should fallback to September contract (latest available)
    res4 = resolve_active_oi_file("BEL", data_dir=str(d), current_date=datetime.date(2026, 10, 1))
    assert os.path.basename(res4) == "BEL24SEP26FUT.parquet"
    
    # 5. Non-matching symbol
    res5 = resolve_active_oi_file("DIXON", data_dir=str(d), current_date=datetime.date(2026, 8, 10))
    assert res5 is None


