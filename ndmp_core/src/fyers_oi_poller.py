"""
NDMP OS v6.0 - Fyers Live OI Snapshot Poller

Fyers does not expose Open Interest via the quotes API or the history API —
OI is only available through the market depth endpoint, and that endpoint is
single-symbol-per-call (no batching). There is also no historical OI backfill
available from Fyers at any price tier known at time of writing.

Consequence: this poller can only build OI history *going forward* from the
moment it starts running. IntradayOIFeature will have no real buildup_code
signal until enough snapshots accumulate — this is not a bug, it's a hard
constraint of the data source. Verify the depth() response field name ("oi")
and any documented rate limits against the current Fyers API docs before
relying on this in production; this was implemented from published docs, not
against a live account.
"""

import os
import time
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd

from ndmp_core.src.fyers_auth import FyersTokenManager
from ndmp_core.src.exceptions import FyersAPIError, FyersAuthError


class FyersOIPoller:
    """Polls Fyers market depth for a list of F&O futures symbols on an
    interval and appends timestamped OI snapshots to a local parquet store."""

    def __init__(
        self,
        symbols: List[str],
        data_dir: str = "data/oi_history",
        poll_interval_seconds: int = 30,
        token_manager: Optional[FyersTokenManager] = None,
        fyers_client=None,
    ):
        if not symbols:
            raise ValueError("FyersOIPoller requires a non-empty symbol list.")
        self.symbols = symbols
        self.data_dir = data_dir
        self.poll_interval_seconds = poll_interval_seconds
        self.token_manager = token_manager or FyersTokenManager()
        # Injectable for testing; production path builds the real client lazily.
        self._fyers_client = fyers_client
        os.makedirs(self.data_dir, exist_ok=True)

    def _get_client(self):
        if self._fyers_client is not None:
            return self._fyers_client
        try:
            from fyers_apiv3 import fyersModel
        except ImportError as e:
            raise FyersAPIError(
                "fyers-apiv3 is not installed. Add it to pyproject.toml dependencies "
                "before running the poller."
            ) from e

        token = self.token_manager.get_access_token()
        client_id = os.environ.get("FYERS_CLIENT_ID")
        if not client_id:
            raise FyersAuthError("Missing required env var: FYERS_CLIENT_ID")

        self._fyers_client = fyersModel.FyersModel(
            client_id=client_id, token=token, is_async=False, log_path=""
        )
        return self._fyers_client

    def poll_once(self) -> pd.DataFrame:
        """Poll depth() for every symbol once and persist each snapshot.
        Raises FyersAPIError on the first failed/malformed symbol response —
        this deliberately does not silently skip bad data."""
        client = self._get_client()
        rows = []
        snapshot_ts = datetime.now(timezone.utc)

        for symbol in self.symbols:
            try:
                resp = client.depth(data={"symbol": symbol, "ohlcv_flag": 1})
            except Exception as e:
                raise FyersAPIError(f"Fyers depth() call failed for {symbol}: {e}") from e

            if not isinstance(resp, dict) or resp.get("s") != "ok":
                raise FyersAPIError(
                    f"Fyers depth() returned a non-ok response for {symbol}: {resp}"
                )

            symbol_data = resp.get("d", {}).get(symbol, {})
            oi = symbol_data.get("oi")
            if oi is None:
                raise FyersAPIError(
                    f"Fyers depth() response for {symbol} has no 'oi' field. "
                    f"Verify the response schema against current Fyers API docs — "
                    f"the field name or endpoint may have changed."
                )

            rows.append({"timestamp": snapshot_ts, "symbol": symbol, "open_interest": oi})

        snapshot_df = pd.DataFrame(rows)
        self._persist(snapshot_df)
        return snapshot_df

    def _persist(self, snapshot_df: pd.DataFrame) -> None:
        """Append this cycle's snapshots to each symbol's parquet history file."""
        for symbol, group in snapshot_df.groupby("symbol"):
            path = os.path.join(self.data_dir, f"{symbol}.parquet")
            if os.path.exists(path):
                existing = pd.read_parquet(path)
                combined = pd.concat([existing, group], ignore_index=True)
            else:
                combined = group
            combined.to_parquet(path, index=False)

    def run_forever(self) -> None:
        """Blocking loop — polls at poll_interval_seconds until interrupted.
        Intended to run as its own long-lived process, separate from the
        3:20 PM scanner cron in local_scheduler.py."""
        import pytz
        from ndmp_core.src.trading_calendar import NSETradingCalendar

        calendar = NSETradingCalendar()
        tz_ist = pytz.timezone("Asia/Kolkata")

        while True:
            now_ist = datetime.now(tz_ist)
            if calendar.is_market_open(now_ist):
                self.poll_once()
            else:
                print(
                    f"[{now_ist.strftime('%Y-%m-%d %H:%M:%S')}] Market is closed (weekend, holiday, or non-market hours). Skipping poll.",
                    flush=True,
                )
            time.sleep(self.poll_interval_seconds)
