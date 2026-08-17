"""
NDMP OS v6.0 - Angel One Instrument Lookup

Angel One's SmartAPI identifies instruments by a numeric "symboltoken", not by
a plain symbol string like Fyers' "NSE:RELIANCE-EQ" convention. Tokens are
resolved via Angel One's publicly published instrument master (a large JSON
covering all tradable instruments across exchanges), refreshed periodically.

VERIFY BEFORE TRUSTING IN PRODUCTION: the instrument master URL and its JSON
schema (fields used below: "token", "symbol", "name", "exch_seg",
"instrumenttype", "expiry") were built from published Angel One
docs/community sources, not tested against a live fetch. Confirm the URL is
still current and the field names match before relying on this.
"""

import os
import json
import time
from typing import Dict, List, Optional

import requests

from ndmp_core.src.exceptions import AngelOneInstrumentLookupError

INSTRUMENT_MASTER_URL = (
    "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
)


class AngelOneInstrumentLookup:
    """Fetches (and locally caches) Angel One's instrument master, and resolves
    a trading symbol + exchange segment to its numeric symboltoken."""

    def __init__(self, cache_path: str = "data/angelone_instrument_master.json",
                 cache_max_age_seconds: int = 24 * 3600):
        self.cache_path = cache_path
        self.cache_max_age_seconds = cache_max_age_seconds
        self._instruments: Optional[List[dict]] = None

    def _load_instruments(self) -> List[dict]:
        if self._instruments is not None:
            return self._instruments

        if os.path.exists(self.cache_path):
            age = time.time() - os.path.getmtime(self.cache_path)
            if age < self.cache_max_age_seconds:
                with open(self.cache_path, "r") as f:
                    self._instruments = json.load(f)
                return self._instruments

        try:
            resp = requests.get(INSTRUMENT_MASTER_URL, timeout=30)
            resp.raise_for_status()
            instruments = resp.json()
        except requests.RequestException as e:
            raise AngelOneInstrumentLookupError(
                f"Failed to fetch Angel One instrument master: {e}"
            ) from e
        except ValueError as e:
            raise AngelOneInstrumentLookupError(
                f"Angel One instrument master response was not valid JSON: {e}"
            ) from e

        os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
        with open(self.cache_path, "w") as f:
            json.dump(instruments, f)

        self._instruments = instruments
        return instruments

    def resolve_token(self, trading_symbol: str, exch_seg: str = "NSE") -> str:
        """Return the numeric symboltoken for an exact trading symbol match
        within the given exchange segment (e.g. 'NSE', 'NFO')."""
        instruments = self._load_instruments()
        matches = [
            inst for inst in instruments
            if inst.get("symbol") == trading_symbol and inst.get("exch_seg") == exch_seg
        ]
        if not matches:
            raise AngelOneInstrumentLookupError(
                f"No Angel One instrument found for symbol={trading_symbol!r} "
                f"exch_seg={exch_seg!r}. Verify the exact trading symbol string "
                f"(e.g. current futures expiry) against the instrument master."
            )
        if len(matches) > 1:
            raise AngelOneInstrumentLookupError(
                f"Ambiguous match for symbol={trading_symbol!r} exch_seg={exch_seg!r}: "
                f"{len(matches)} instruments matched. Narrow the lookup (e.g. by expiry)."
            )
        return matches[0]["token"]

    def resolve_tokens(self, symbols: List[Dict[str, str]]) -> Dict[str, str]:
        """Batch version: symbols is a list of {'symbol': ..., 'exch_seg': ...}.
        Returns {symbol: token}. Raises on the first unresolvable symbol —
        does not silently skip missing ones."""
        return {
            s["symbol"]: self.resolve_token(s["symbol"], s.get("exch_seg", "NSE"))
            for s in symbols
        }
