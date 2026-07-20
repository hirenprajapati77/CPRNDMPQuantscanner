"""
NDMP OS v6.0 - Yahoo Finance Live Data Downloader
Downloads actual live market data from Yahoo Finance and formats it for the scanner.
"""

import os
import subprocess
import sys
import pandas as pd

# Check and install yfinance dynamically if not present
try:
    import yfinance as yf
except ImportError:
    print("[Ingestion] Installing yfinance...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance"])
    import yfinance as yf


def download_symbol_data(ticker: str, start_date: str = "2026-06-01") -> pd.DataFrame:
    print(f"Downloading {ticker} from Yahoo Finance...")
    # Fetch daily price data
    stock = yf.Ticker(ticker)
    df = stock.history(start=start_date, interval="1d")
    
    if df.empty:
        raise ValueError(f"No data returned for ticker {ticker}")
        
    df = df.reset_index()
    
    # Map column names to NDMP OS schema requirements
    # yfinance uses 'Date' or 'Datetime' depending on interval
    date_col = "Date" if "Date" in df.columns else "Datetime"
    
    # Format timestamp to string
    df["timestamp"] = df[date_col].dt.strftime("%Y-%m-%d %H:%M:%S")
    
    # Calculate VWAP proxy (typical price) since public yfinance doesn't provide broker VWAP
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3.0
    
    result_df = pd.DataFrame({
        "timestamp": df["timestamp"],
        "symbol": [ticker.split(".")[0]] * len(df),
        "open": df["Open"],
        "high": df["High"],
        "low": df["Low"],
        "close": df["Close"],
        "volume": df["Volume"],
        # Mock Open Interest since it's not present in free equity feeds
        "open_interest": [100000] * len(df),
        "vwap": typical_price
    })
    
    return result_df


def main():
    data_dir = "data/parquet"
    os.makedirs(data_dir, exist_ok=True)
    
    # Tickers on Yahoo Finance for NSE (Indian stock market suffixes '.NS')
    tickers = {
        "BEL": "BEL.NS",
        "TRENT": "TRENT.NS",
        "DIXON": "DIXON.NS",
        "NIFTY": "^NSEI"  # Nifty 50 Index
    }
    
    try:
        # 1. Download benchmark first
        nifty_df = download_symbol_data(tickers["NIFTY"])
        nifty_path = os.path.join(data_dir, "NIFTY.parquet")
        nifty_df.to_parquet(nifty_path, index=False)
        print(f"Saved benchmark to: {nifty_path}")
        
        # Keep a mapping of timestamp -> benchmark_close
        nifty_map = nifty_df.set_index("timestamp")["close"].to_dict()
        
        # 2. Download stocks and merge benchmark close
        for symbol, ticker in tickers.items():
            if symbol == "NIFTY":
                continue
                
            stock_df = download_symbol_data(ticker)
            # Map benchmark_close safely by date
            stock_df["benchmark_close"] = stock_df["timestamp"].map(nifty_map)
            # Fill missing benchmark values if any
            stock_df["benchmark_close"] = stock_df["benchmark_close"].ffill().bfill()
            
            path = os.path.join(data_dir, f"{symbol}.parquet")
            stock_df.to_parquet(path, index=False)
            print(f"Saved {symbol} to: {path}")
            
        print("\n[INGESTION SUCCESS] Actual live market data downloaded and saved locally.")
        
    except Exception as e:
        print(f"\n[INGESTION ERROR] Failed to fetch live data: {str(e)}")


if __name__ == "__main__":
    main()
