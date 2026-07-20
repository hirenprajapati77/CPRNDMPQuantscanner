"""
NDMP OS v6.0 - IntradayOIFeature Plugin
Calculates Intraday Open Interest change percentage and Price-OI Matrix build-up classification.
"""

from typing import Dict, Any, List
import pandas as pd
import numpy as np
from ndmp_research.features.base_feature import BaseFeature
from ndmp_core.src.exceptions import (
    MissingDependencyError,
    FeatureCalculationError,
    DataSourceIntegrityError,
)


class IntradayOIFeature(BaseFeature):
    """Futures Open Interest & Institutional Build-Up Classification Plugin."""

    def __init__(self, manifest_path: str | None = None):
        super().__init__(feature_id="FEAT_003", manifest_path=manifest_path)

    def dependencies(self) -> List[str]:
        return ["close", "open_interest"]

    def version(self) -> str:
        return "1.0.0"

    def metadata(self) -> Dict[str, Any]:
        return {
            "id": self.feature_id,
            "name": "IntradayOIFeature",
            "version": self.version(),
            "category": "FuturesOI",
            "dependencies": self.dependencies()
        }

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        for dep in self.dependencies():
            if dep not in df.columns:
                raise MissingDependencyError(f"IntradayOIFeature missing required column: {dep}")

        # Guard: a real Futures OI feed varies intraday/day-to-day. A constant or
        # all-NaN series (e.g. yfinance equity data, which has no OI field and must
        # not be backfilled with a placeholder) silently forces buildup_code to 0
        # (Neutral) for every row, zeroing out its +15pt weight in RankingEngine
        # without any visible error. Fail loudly instead of scoring on dead data.
        oi = df["open_interest"]
        if oi.isna().all() or oi.nunique(dropna=True) <= 1:
            raise DataSourceIntegrityError(
                "IntradayOIFeature received a constant or all-NaN 'open_interest' "
                "series — this data source does not provide real Futures OI. "
                "Route this symbol through a real OI feed (e.g. Fyers futures API) "
                "or exclude IntradayOIFeature from scoring for this data source."
            )

        try:
            price_change = df["close"].diff().fillna(0.0)
            oi_change = df["open_interest"].diff().fillna(0.0)
            oi_change_pct = df["open_interest"].pct_change().fillna(0.0) * 100.0

            # Build-Up Matrix Classification (Strict Boundary Logic):
            # 1: Long Build-up (Price > 0, OI > 0)
            # 2: Short Covering (Price > 0, OI < 0)
            # 3: Short Build-up (Price < 0, OI > 0)
            # 4: Long Unwinding (Price < 0, OI < 0)
            # 0: Neutral / No Change (Price == 0 or OI == 0)
            buildup_code = np.zeros(len(df), dtype=int)
            buildup_code[(price_change > 0) & (oi_change > 0)] = 1   # Long Build-up
            buildup_code[(price_change > 0) & (oi_change < 0)] = 2   # Short Covering
            buildup_code[(price_change < 0) & (oi_change > 0)] = 3   # Short Build-up
            buildup_code[(price_change < 0) & (oi_change < 0)] = 4   # Long Unwinding

            return pd.DataFrame({
                "oi_change_pct": oi_change_pct,
                "buildup_code": buildup_code
            }, index=df.index)
        except Exception as e:
            raise FeatureCalculationError(f"IntradayOIFeature calculation failed: {str(e)}") from e

    def validate(self, series: pd.Series | pd.DataFrame) -> bool:
        if isinstance(series, pd.DataFrame):
            return not series["oi_change_pct"].isnull().any()
        return not series.isnull().any()
