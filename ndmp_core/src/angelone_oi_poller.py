"""
NDMP OS v6.0 - Angel One Live OI Snapshot Poller

Unlike Fyers (single-symbol depth() calls only), Angel One's getMarketData()
in FULL mode returns Open Interest for up to 50 symbols in a single batched
request. This poller takes advantage of that: one call per cycle covers the
whole candidate list, rather than one call per symbol per cycle.

Same hard constraint as the Fyers poller: no historical OI backfill exists
for Angel One either — this only builds history *forward* from when it
starts running.

VERIFY BEFORE TRUSTING IN PRODUCTION: the getMarketData() request/response
shape (mode="FULL", exchangeTokens dict, response field "opnInterest") was
built from published Angel One docs, not tested against a live account.
Confirm the exact field name and response structure on first real run.
"""

import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

from ndmp_core.src.angelone_auth import AngelOneSessionManager
from ndmp_core.src.angelone_instrument_lookup import AngelOneInstrumentLookup
from ndmp_core.src.exceptions import AngelOneAPIError, AngelOneAuthError


class AngelOneOIPoller:
    """Polls Angel One's batched market data endpoint for a list of symbols
    on an interval and appends timestamped OI snapshots to a local parquet
    store — one file per symbol, same layout as the Fyers poller used."""

    def __init__(
        self,
        symbols: List[Dict[str, str]],  # [{"symbol": "BEL26AUGFUT", "exch_seg": "NFO"}, ...]
        data_dir: str = "data/oi_history_angelone",
        poll_interval_seconds: int = 30,
        session_manager: Optional[AngelOneSessionManager] = None,
        instrument_lookup: Optional[AngelOneInstrumentLookup] = None,
        smart_api_client=None,
    ):
        if not symbols:
            raise ValueError("AngelOneOIPoller requires a non-empty symbol list.")
        self.symbols = symbols
        self.data_dir = data_dir
        self.poll_interval_seconds = poll_interval_seconds
        self.session_manager = session_manager or AngelOneSessionManager()
        self.instrument_lookup = instrument_lookup or AngelOneInstrumentLookup()
        # Injectable for testing; production path builds the real client lazily.
        self._smart_api_client = smart_api_client
        os.makedirs(self.data_dir, exist_ok=True)

    def _get_client(self):
        if self._smart_api_client is not None:
            return self._smart_api_client
        try:
            from SmartApi import SmartConnect
        except ImportError as e:
            raise AngelOneAPIError(
                "smartapi-python is not installed. Add it to pyproject.toml "
                "dependencies before running the poller."
            ) from e

        access_token = self.session_manager.get_access_token()
        api_key = os.environ.get("ANGELONE_API_KEY")
        if not api_key:
            raise AngelOneAuthError("Missing required env var: ANGELONE_API_KEY")

        # Fetch public IP dynamically to bypass SmartAPI's hardcoded 'finally' block IP bug
        import requests
        try:
            public_ip = requests.get("https://api.ipify.org", timeout=5).text.strip()
        except Exception:
            public_ip = "127.0.0.1"

        client = SmartConnect(api_key=api_key)

        # Instance-Level override
        client.clientPublicIp = public_ip
        client.clientPublicIP = public_ip

        # Clean prefix "Bearer " since the API client's setAccessToken adds it manually
        if access_token.startswith("Bearer "):
            access_token = access_token.replace("Bearer ", "").strip()

        client.setAccessToken(access_token)
        self._smart_api_client = client
        return self._smart_api_client

    def poll_once(self) -> pd.DataFrame:
        """Poll getMarketData() once for all symbols (batched, single call) and
        persist each snapshot. Raises AngelOneAPIError on a non-ok response —
        this deliberately does not silently skip bad data."""
        client = self._get_client()
        snapshot_ts = datetime.now(timezone.utc)

        by_exch_seg: Dict[str, List[str]] = {}
        token_to_symbol: Dict[str, str] = {}
        for s in self.symbols:
            token = self.instrument_lookup.resolve_token(s["symbol"], s.get("exch_seg", "NSE"))
            by_exch_seg.setdefault(s.get("exch_seg", "NSE"), []).append(token)
            token_to_symbol[token] = s["symbol"]

        try:
            resp = client.getMarketData(mode="FULL", exchangeTokens=by_exch_seg)
        except Exception as e:
            raise AngelOneAPIError(f"Angel One getMarketData() call failed: {e}") from e

        if not isinstance(resp, dict) or not resp.get("status"):
            raise AngelOneAPIError(f"Angel One getMarketData() returned a non-ok response: {resp}")

        fetched = resp.get("data", {}).get("fetched", [])
        rows = []
        seen_tokens = set()
        for item in fetched:
            token = item.get("symbolToken")
            oi = item.get("opnInterest")
            if oi is None:
                raise AngelOneAPIError(
                    f"Angel One getMarketData() response for token {token} has no "
                    f"'opnInterest' field. Verify the response schema against current "
                    f"Angel One API docs — the field name may have changed."
                )
            symbol = token_to_symbol.get(token, token)
            rows.append({"timestamp": snapshot_ts, "symbol": symbol, "open_interest": oi})
            seen_tokens.add(token)

        missing = set(token_to_symbol) - seen_tokens
        if missing:
            missing_symbols = [token_to_symbol[t] for t in missing]
            raise AngelOneAPIError(
                f"Angel One getMarketData() response did not include data for: "
                f"{missing_symbols}. Not persisting a partial snapshot."
            )

        snapshot_df = pd.DataFrame(rows)
        self._persist(snapshot_df)
        return snapshot_df

    def _persist(self, snapshot_df: pd.DataFrame) -> None:
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
        Skips polling outside NSE market hours/trading days (weekends,
        holidays) rather than attempting calls that will just fail — same
        gating pattern as fyers_oi_poller.py's run_forever."""
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
                    f"[{now_ist.strftime('%Y-%m-%d %H:%M:%S')}] Market is closed "
                    f"(weekend, holiday, or non-market hours). Skipping poll.",
                    flush=True,
                )
            time.sleep(self.poll_interval_seconds)
