import os
import subprocess
import sys
import pandas as pd
import concurrent.futures
import glob
import datetime
import re

MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
}

def resolve_active_oi_file(symbol: str, data_dir: str = "data/oi_history_angelone", current_date: datetime.date = None) -> str:
    if current_date is None:
        current_date = datetime.date.today()
    
    if not os.path.exists(data_dir):
        return None
        
    pattern = re.compile(rf"^{symbol}(\d{{2}})([A-Z]{{3}})(\d{{2}})FUT\.parquet$")
    oi_files = []
    
    for fname in os.listdir(data_dir):
        match = pattern.match(fname)
        if match:
            day_str, month_str, year_str = match.groups()
            month_num = MONTHS.get(month_str)
            if month_num:
                year_num = 2000 + int(year_str)
                day_num = int(day_str)
                try:
                    expiry_date = datetime.date(year_num, month_num, day_num)
                    oi_files.append((expiry_date, os.path.join(data_dir, fname)))
                except ValueError:
                    continue
                    
    if not oi_files:
        return None
        
    valid_files = [x for x in oi_files if x[0] >= current_date]
    if valid_files:
        valid_files.sort(key=lambda x: x[0])
        return valid_files[0][1]
    else:
        # Fallback to the latest available expiry in the past
        oi_files.sort(key=lambda x: x[0], reverse=True)
        return oi_files[0][1]


# Check and install yfinance dynamically if not present
try:
    import yfinance as yf
except ImportError:
    print("[Ingestion] Installing yfinance...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance"])
    import yfinance as yf


DOWNLOAD_TIMEOUT_SECS = 60  # Hard per-ticker timeout to prevent VM freeze


def _fetch_history(ticker: str, start_date: str) -> pd.DataFrame:
    """Inner blocking call — run inside a thread with a timeout."""
    stock = yf.Ticker(ticker)
    df = stock.history(start=start_date, interval="1d")
    if df.empty:
        raise ValueError(f"No data returned for ticker {ticker}")
    return df


def download_symbol_data(ticker: str, start_date: str = "2026-06-01") -> pd.DataFrame:
    print(f"Downloading {ticker} from Yahoo Finance...")
    # Run inside a thread so we can enforce a hard timeout
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_fetch_history, ticker, start_date)
        try:
            df = future.result(timeout=DOWNLOAD_TIMEOUT_SECS)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(
                f"[TIMEOUT] {ticker} download exceeded {DOWNLOAD_TIMEOUT_SECS}s — "
                "Yahoo Finance may be unresponsive. Skipping."
            )
    
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
        # Yahoo Finance equity data has no Futures OI field. Previously this was
        # backfilled with a constant placeholder (100000), which silently forced
        # IntradayOIFeature's buildup_code to 0 (Neutral) for every row — zeroing
        # out its +15pt scoring weight with no visible error. Emit NaN instead so
        # IntradayOIFeature's data-integrity guard raises DataSourceIntegrityError
        # rather than scoring on fake data. Real OI must come from a futures feed
        # (e.g. Fyers) before this feature can be trusted for this symbol.
        "open_interest": [float("nan")] * len(df),
        "vwap": typical_price
    })
    
    return result_df


def merge_open_interest(stock_df: pd.DataFrame, oi_df: pd.DataFrame) -> pd.DataFrame:
    """Align and merge Angel One Open Interest data into Yahoo Finance stock DataFrame.
    Filters to pull the last snapshot between 15:15 and 15:30 IST (market close window) per day.
    Leaves gap days and dates before data collection as NaN (no look-ahead bfill or ffill).
    """
    import numpy as np
    if oi_df.empty:
        stock_df = stock_df.copy()
        stock_df["open_interest"] = np.nan
        return stock_df
        
    # Convert UTC timestamps to datetime, then to Asia/Kolkata timezone (IST)
    oi_df = oi_df.copy()
    oi_df["datetime_ist"] = pd.to_datetime(oi_df["timestamp"]).dt.tz_convert("Asia/Kolkata")
    oi_df["date"] = oi_df["datetime_ist"].dt.date
    oi_df["time"] = oi_df["datetime_ist"].dt.time
    
    # Filter for snapshots >= 15:15 IST (market close window or EOD recovery)
    min_market_time = datetime.time(15, 15, 0)
    oi_df_filtered = oi_df[oi_df["time"] >= min_market_time]
    
    stock_df = stock_df.copy()
    if oi_df_filtered.empty:
        stock_df["open_interest"] = np.nan
        return stock_df
        
    # Group by date and take the last snapshot's open_interest
    daily_oi = oi_df_filtered.groupby("date")["open_interest"].last().to_dict()
    
    # Map to stock_df using date component of timestamp
    stock_df["date_parsed"] = pd.to_datetime(stock_df["timestamp"]).dt.date
    stock_df["open_interest"] = stock_df["date_parsed"].map(daily_oi)
    stock_df = stock_df.drop(columns=["date_parsed"])
    
    return stock_df


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
        
    except (TimeoutError, Exception) as e:
        print(f"\n[INGESTION ERROR] Failed to fetch benchmark NIFTY: {str(e)}")
        return

    # 2. Download stocks and merge benchmark close
    success_count = 0
    for symbol, ticker in tickers.items():
        if symbol == "NIFTY":
            continue
        try:
            stock_df = download_symbol_data(ticker)
            # Map benchmark_close safely by date
            stock_df["benchmark_close"] = stock_df["timestamp"].map(nifty_map)
            # Fill missing benchmark values if any
            stock_df["benchmark_close"] = stock_df["benchmark_close"].ffill().bfill()
            
            # Map real Open Interest from Angel One poller if available
            oi_path = resolve_active_oi_file(symbol)
            if oi_path:
                print(f"Mapping real Open Interest from {oi_path} for {symbol}...")
                oi_df = pd.read_parquet(oi_path)
                stock_df = merge_open_interest(stock_df, oi_df)
            else:
                import numpy as np
                stock_df["open_interest"] = np.nan
            
            path = os.path.join(data_dir, f"{symbol}.parquet")
            stock_df.to_parquet(path, index=False)
            print(f"Saved {symbol} to: {path}")
            success_count += 1
        except TimeoutError as e:
            print(f"  [SKIP] {symbol}: {str(e)}")
        except Exception as e:
            print(f"  [ERROR] {symbol}: {str(e)}")

    if success_count > 0:
        print(f"\n[INGESTION SUCCESS] {success_count}/{len(tickers)-1} symbols downloaded.")
    else:
        print("\n[INGESTION ERROR] No symbols downloaded successfully.")


if __name__ == "__main__":
    main()
