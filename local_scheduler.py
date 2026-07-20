"""
NDMP OS v6.0 - Local Scheduling Daemon
Monitors system clock and automatically triggers the scanner at 15:20 IST.
"""

import time
import subprocess
import os
from datetime import datetime


def is_trading_day() -> bool:
    # Monday = 0, Friday = 4, Saturday = 5, Sunday = 6
    weekday = datetime.now().weekday()
    return weekday < 5


def run_scanner_job():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Triggering scanner execution...")
    try:
        res = subprocess.run(["python", "run_scanner.py"], capture_output=True, text=True, check=True)
        print(res.stdout)
    except subprocess.CalledProcessError as e:
        print(f"[JOB ERROR] Scanner run failed with exit code {e.returncode}:")
        print(e.stderr)


def main():
    print("=" * 80)
    print("NDMP OS v6.0 - LOCAL SHADOW MODE SCHEDULER DAEMON")
    print("=" * 80)
    print("Status: RUNNING")
    print("Target: 15:20:00 Local Time (IST equivalent)")
    print("Ensure live data ingestion writes to data/parquet/ before this time.")
    print("Press Ctrl+C to stop.")
    print("=" * 80)
    
    target_hour = 15
    target_minute = 20
    
    # Initialize last_run_date from the most recent journal file at startup to prevent double-runs
    import glob
    last_run_date = None
    journals = sorted(glob.glob("ndmp_knowledge/journal/decisions_*.json"))
    if journals:
        last_file = os.path.basename(journals[-1])
        parts = last_file.split("_")
        if len(parts) >= 2:
            date_str = parts[1]  # YYYYMMDD
            last_run_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            print(f"Detected previous scan for date: {last_run_date}")
            
    while True:
        now = datetime.now()
        current_date_str = now.strftime("%Y-%m-%d")
            
        if is_trading_day():
            if now.hour == target_hour and now.minute == target_minute and last_run_date != current_date_str:
                run_scanner_job()
                last_run_date = current_date_str
                
        # Sleep 10 seconds between checks
        time.sleep(10)


if __name__ == "__main__":
    main()
