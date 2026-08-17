"""
NDMP OS v6.0 - Local Scheduling Daemon
Monitors system clock and automatically triggers the scanner at 15:20 IST (09:50 UTC).
"""

import glob
import os
import subprocess
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ndmp_core.src.trading_calendar import NSETradingCalendar

IST = ZoneInfo("Asia/Kolkata")
SCAN_HOUR_UTC = 9
SCAN_MINUTE_UTC = 50


def run_scanner_job():
    print(f"\n[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC] Triggering scanner execution...")
    try:
        res = subprocess.run(["python", "run_scanner.py"], capture_output=True, text=True, check=True)
        print(res.stdout)
    except subprocess.CalledProcessError as e:
        print(f"[JOB ERROR] Scanner run failed with exit code {e.returncode}:")
        print(e.stderr)


def load_last_run_date_from_journal() -> str | None:
    """Parse UTC date from the most recent decision journal filename."""
    journals = sorted(glob.glob("ndmp_knowledge/journal/decisions_*.json"))
    if not journals:
        return None
    parts = os.path.basename(journals[-1]).split("_")
    if len(parts) < 2:
        return None
    date_str = parts[1]
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"


def main():
    print("=" * 80)
    print("NDMP OS v6.0 - LOCAL SHADOW MODE SCHEDULER DAEMON")
    print("=" * 80)
    print("Status: RUNNING")
    print("Target: 15:20 IST (09:50 UTC)")
    print("Ensure live data ingestion writes to data/parquet/ before this time.")
    print("Press Ctrl+C to stop.")
    print("=" * 80)

    calendar = NSETradingCalendar()
    last_run_date = load_last_run_date_from_journal()
    if last_run_date:
        print(f"Detected previous scan for UTC date: {last_run_date}")

    while True:
        now_utc = datetime.now(timezone.utc)
        current_date_str = now_utc.strftime("%Y-%m-%d")
        ist_date = now_utc.astimezone(IST).date()

        if calendar.is_trading_day(ist_date):
            if (
                now_utc.hour == SCAN_HOUR_UTC
                and now_utc.minute == SCAN_MINUTE_UTC
                and last_run_date != current_date_str
            ):
                run_scanner_job()
                last_run_date = current_date_str

        time.sleep(10)


if __name__ == "__main__":
    main()
