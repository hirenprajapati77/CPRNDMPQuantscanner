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
    
    last_run_date = None
    
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
