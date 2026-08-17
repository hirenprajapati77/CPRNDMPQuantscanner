"""
NDMP OS v6.0 - Observation Journal (OI Signal Validation)

buildup_code already carries live scoring weight in RankingEngine (+15/+8/-15
depending on classification) — it is NOT in shadow mode the way BTST V2 is on
CPR Pro. This journal exists to answer the actual question that motivated
adding OI in the first place: does it improve ranking quality, or not?

Design: two append-only files per symbol, never mutated in place.
  - {symbol}_signals.parquet   — written same-day, at scan time
  - {symbol}_outcomes.parquet  — written the following trading day, once the
                                  next close is known

full_score is what RankingEngine actually produced (OI-inclusive). baseline_score
is the same StockSignals re-scored with buildup_code forced to 0 (Neutral) —
this is what makes it possible to later ask "would a pure price-structure
ranking have picked differently?" rather than only "how did today's actual
ranking do?", which would be a self-fulfilling question.

NOTE: three symbols over a few weeks is directional signal, not a
statistically meaningful backtest. Don't over-read small differences here.
"""

import os
from datetime import date as date_type
from typing import List, Optional

import pandas as pd

from ndmp_core.src.ranking_engine import RankingEngine, RankedCandidate
from ndmp_core.src.exceptions import NDMPError


class ObservationJournalError(NDMPError):
    """Raised on malformed inputs to the observation journal (not a
    data-quality gate — this journal is observational, not scoring-critical,
    so it fails loud on bad inputs but is never allowed to affect ranking)."""
    pass


class ObservationJournal:
    """Logs daily signals (with a baseline-vs-full score split) and resolves
    next-day outcomes, for later analysis of whether OI improves ranking."""

    def __init__(self, journal_dir: str = "data/observation_journal"):
        self.journal_dir = journal_dir
        os.makedirs(self.journal_dir, exist_ok=True)

    def _signals_path(self, symbol: str) -> str:
        return os.path.join(self.journal_dir, f"{symbol}_signals.parquet")

    def _outcomes_path(self, symbol: str) -> str:
        return os.path.join(self.journal_dir, f"{symbol}_outcomes.parquet")

    def log_signals(self, ranked_candidates: List[RankedCandidate], scan_date: str) -> None:
        """Log one row per candidate for today's scan. scan_date should be an
        ISO date string (YYYY-MM-DD) — the trading day being scored, not a
        timestamp. Safe to call once per day per symbol; calling twice for
        the same (symbol, scan_date) will create a duplicate row, since this
        is append-only by design — callers should not re-run a day's scan
        after journaling it."""
        for rc in ranked_candidates:
            baseline_signals = rc.signals.model_copy(update={"buildup_code": 0})
            baseline_score = RankingEngine.calculate_score(baseline_signals)

            row = pd.DataFrame([{
                "date": scan_date,
                "symbol": rc.symbol,
                "close": rc.signals.close,
                "buildup_code": rc.signals.buildup_code,
                "full_score": rc.score,
                "baseline_score": baseline_score,
            }])

            path = self._signals_path(rc.symbol)
            if os.path.exists(path):
                existing = pd.read_parquet(path)
                combined = pd.concat([existing, row], ignore_index=True)
            else:
                combined = row
            combined.to_parquet(path, index=False)

    def resolve_outcomes(self, symbol: str, ohlcv_df: pd.DataFrame) -> pd.DataFrame:
        """Resolve any signal dates for `symbol` whose next trading day's OHLCV
        is now available in `ohlcv_df` (expects columns: timestamp/date-like,
        open, high, low, close). Idempotent — already-resolved dates are
        skipped, not reprocessed. Returns the newly-resolved rows (empty
        DataFrame if nothing new was resolvable)."""
        signals_path = self._signals_path(symbol)
        if not os.path.exists(signals_path):
            return pd.DataFrame()

        signals_df = pd.read_parquet(signals_path)
        outcomes_path = self._outcomes_path(symbol)
        already_resolved = set()
        if os.path.exists(outcomes_path):
            existing_outcomes = pd.read_parquet(outcomes_path)
            already_resolved = set(existing_outcomes["date"].astype(str))

        ohlcv = ohlcv_df.copy()
        ohlcv["date"] = pd.to_datetime(ohlcv["timestamp"]).dt.date.astype(str)
        ohlcv = ohlcv.sort_values("date").reset_index(drop=True)
        date_to_idx = {d: i for i, d in enumerate(ohlcv["date"])}

        new_rows = []
        for _, sig_row in signals_df.iterrows():
            sig_date = str(sig_row["date"])
            if sig_date in already_resolved:
                continue
            if sig_date not in date_to_idx:
                continue  # signal date itself not in OHLCV — nothing to resolve against yet
            idx = date_to_idx[sig_date]
            if idx + 1 >= len(ohlcv):
                continue  # next trading day hasn't happened yet

            next_row = ohlcv.iloc[idx + 1]
            prior_close = float(sig_row["close"])
            next_open = float(next_row["open"])
            next_close = float(next_row["close"])
            next_high = float(next_row["high"])
            next_low = float(next_row["low"])

            new_rows.append({
                "date": sig_date,
                "symbol": symbol,
                "next_day_open": next_open,
                "next_day_high": next_high,
                "next_day_low": next_low,
                "next_day_close": next_close,
                "next_day_return_pct": round((next_close - prior_close) / prior_close * 100.0, 4),
                "gap_pct": round((next_open - prior_close) / prior_close * 100.0, 4),
            })

        if not new_rows:
            return pd.DataFrame()

        new_df = pd.DataFrame(new_rows)
        if os.path.exists(outcomes_path):
            existing = pd.read_parquet(outcomes_path)
            combined = pd.concat([existing, new_df], ignore_index=True)
        else:
            combined = new_df
        combined.to_parquet(outcomes_path, index=False)

        return new_df
