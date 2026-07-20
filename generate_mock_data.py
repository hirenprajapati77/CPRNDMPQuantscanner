"""
NDMP OS v6.0 - Mock Data Generator
Generates mock historical Parquet files in data/parquet for local testing and validation.
"""

import os
import pandas as pd
import numpy as np


def generate_mock_ohlcv(symbol: str, dates: pd.DatetimeIndex, start_price: float, is_nifty: bool = False) -> pd.DataFrame:
    """Generate mock price and volume data."""
    n = len(dates)
    np.random.seed(hash(symbol) % 123456)
    
    closes = [start_price]
    for _ in range(1, n):
        change = np.random.normal(0.0005, 0.008)  # slight upward drift
        closes.append(closes[-1] * (1.0 + change))
        
    closes = np.array(closes)
    highs = closes * (1.0 + np.random.uniform(0.001, 0.015, size=n))
    lows = closes * (1.0 - np.random.uniform(0.001, 0.015, size=n))
    opens = np.zeros(n)
    opens[0] = start_price
    opens[1:] = closes[:-1]
    
    volumes = np.random.randint(5000, 50000, size=n)
    oi = np.random.randint(100000, 500000, size=n)
    vwap = closes + np.random.normal(0, 0.5, size=n)
    
    df = pd.DataFrame({
        "timestamp": dates,
        "symbol": [symbol] * n,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
        "open_interest": oi,
        "vwap": vwap
    })
    
    if not is_nifty:
        # Add delivery volume column
        df["delivery_volume"] = (df["volume"] * np.random.uniform(0.3, 0.7, size=n)).astype(int)
        
    return df


def main():
    data_dir = "data/parquet"
    os.makedirs(data_dir, exist_ok=True)
    
    print(f"[DATA GENERATOR] Generating mock datasets in '{data_dir}'...")
    dates = pd.date_range("2026-07-16 09:15:00", "2026-07-20 15:30:00", freq="15min")
    # Filter only market hours (09:15 to 15:30)
    dates = dates[(dates.time >= pd.Timestamp("09:15").time()) & (dates.time <= pd.Timestamp("15:30").time())]
    
    # 1. Generate Nifty benchmark close
    df_nifty = generate_mock_ohlcv("NIFTY", dates, 24000.0, is_nifty=True)
    nifty_path = os.path.join(data_dir, "NIFTY.parquet")
    df_nifty.to_parquet(nifty_path, index=False)
    print(f"Generated Nifty benchmark: {nifty_path}")

    # 2. Generate stock data
    stocks = [
        ("BEL", 280.0),
        ("TRENT", 5000.0),
        ("DIXON", 11800.0)
    ]
    
    for symbol, price in stocks:
        df_stock = generate_mock_ohlcv(symbol, dates, price)
        # Add benchmark_close column required by RelativeStrengthFeature
        df_stock["benchmark_close"] = df_nifty["close"].values
        
        path = os.path.join(data_dir, f"{symbol}.parquet")
        df_stock.to_parquet(path, index=False)
        print(f"Generated Stock dataset for {symbol}: {path}")
        
    print("[DATA GENERATOR SUCCESS] Ingestion directory populated successfully.")


if __name__ == "__main__":
    main()
