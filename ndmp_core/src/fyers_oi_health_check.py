"""
NDMP OS v6.0 - Fyers OI Poller Health Check

Standalone check, run on its own systemd timer (independent of the poller
process itself), so a crash-looping poller gets noticed the same day, not
three days later. Checks whether any symbol's parquet file in
data/oi_history/ has been modified recently; if not, during market hours,
sends an alert.

Deliberately does NOT try to fix the poller itself — this only detects and
alerts. Fixing (e.g. restarting, rotating a token) stays a separate,
reviewed action.
"""

import os
import glob
import time
from datetime import datetime
from typing import Optional, Callable

from ndmp_core.src.trading_calendar import NSETradingCalendar


def most_recent_mtime(data_dir: str) -> Optional[float]:
    """Return the most recent modification time across all parquet files in
    data_dir, or None if the directory has no parquet files at all."""
    paths = glob.glob(os.path.join(data_dir, "*.parquet"))
    if not paths:
        return None
    return max(os.path.getmtime(p) for p in paths)


def check_poller_health(
    data_dir: str,
    now_ist: datetime,
    calendar: NSETradingCalendar,
    stale_threshold_seconds: int = 600,
    alert_fn: Optional[Callable[[str], None]] = None,
) -> bool:
    """Returns True if healthy (or market closed, where staleness is expected).
    Returns False and fires alert_fn(message) if snapshots are stale during
    market hours, or if no snapshots exist at all during market hours."""
    if not calendar.is_market_open(now_ist):
        return True  # staleness outside market hours is expected, not a fault

    latest_mtime = most_recent_mtime(data_dir)
    if latest_mtime is None:
        message = (
            f"[FYERS OI HEALTH CHECK] No parquet snapshots found in {data_dir} "
            f"during market hours ({now_ist.isoformat()}). Poller may never have "
            f"started, or the token/auth is failing on every attempt."
        )
        if alert_fn:
            alert_fn(message)
        return False

    age_seconds = time.time() - latest_mtime
    if age_seconds > stale_threshold_seconds:
        message = (
            f"[FYERS OI HEALTH CHECK] Newest OI snapshot in {data_dir} is "
            f"{int(age_seconds)}s old (threshold {stale_threshold_seconds}s), "
            f"during market hours ({now_ist.isoformat()}). Poller is likely "
            f"crash-looping or stuck — check `systemctl status fyers-oi-poller.service` "
            f"and `journalctl -u fyers-oi-poller.service` for the cause."
        )
        if alert_fn:
            alert_fn(message)
        return False

    return True


def default_alert(message: str) -> None:
    """Fallback alert: print to stderr/journal. Replace this with a call into
    whichever channel already carries CPR Pro alerts (Telegram, email, etc.)
    rather than building a new notification path — this is intentionally a
    thin, swappable seam, not the final delivery mechanism."""
    import sys
    print(message, file=sys.stderr, flush=True)


def main():
    import pytz

    data_dir = os.environ.get("FYERS_OI_DATA_DIR", "data/oi_history")
    tz_ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(tz_ist)
    calendar = NSETradingCalendar()

    healthy = check_poller_health(data_dir, now_ist, calendar, alert_fn=default_alert)
    if not healthy:
        raise SystemExit(1)  # non-zero exit so systemd/monitoring can key off it too


if __name__ == "__main__":
    main()
