"""
NDMP OS v6.0 - CPRFeature Plugin
Calculates Frank Ochoa Central Pivot Range (Pivot, TC, BC, CPR Width %, Narrow CPR flag) & Camarilla levels.
"""

from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np
from ndmp_research.features.base_feature import BaseFeature
from ndmp_core.src.exceptions import MissingDependencyError, FeatureCalculationError


class CPRFeature(BaseFeature):
    """CPR & Camarilla Price Geometry Feature Plugin."""

    def __init__(self, manifest_path: str | None = None):
        super().__init__(feature_id="FEAT_001", manifest_path=manifest_path)

    def dependencies(self) -> List[str]:
        return ["high", "low", "close"]

    def version(self) -> str:
        return "1.0.0"

    def metadata(self) -> Dict[str, Any]:
        return {
            "id": self.feature_id,
            "name": "CPRFeature",
            "version": self.version(),
            "category": "PriceGeometry",
            "dependencies": self.dependencies()
        }

    @staticmethod
    def _prior_session_ohlc(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Return prior completed session H/L/C aligned to each row (no look-ahead)."""
        if "timestamp" in df.columns:
            work = df.copy()
            work["_session"] = pd.to_datetime(work["timestamp"]).dt.date
            daily = (
                work.groupby("_session", sort=True)
                .agg(session_high=("high", "max"), session_low=("low", "min"), session_close=("close", "last"))
                .reset_index()
            )
            daily["prior_high"] = daily["session_high"].shift(1)
            daily["prior_low"] = daily["session_low"].shift(1)
            daily["prior_close"] = daily["session_close"].shift(1)
            merged = work.merge(
                daily[["_session", "prior_high", "prior_low", "prior_close"]],
                on="_session",
                how="left",
            )
            return merged["prior_high"], merged["prior_low"], merged["prior_close"]

        return df["high"].shift(1), df["low"].shift(1), df["close"].shift(1)

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate CPR & Camarilla indicators from the PRIOR session's H/L/C.
        Returns DataFrame with ['cpr_pivot', 'cpr_tc', 'cpr_bc', 'cpr_width_pct', 'is_narrow_cpr', 'cam_h3', 'cam_l3', 'cam_h4', 'cam_l4'].
        """
        for dep in self.dependencies():
            if dep not in df.columns:
                raise MissingDependencyError(f"CPRFeature missing required column: {dep}")

        try:
            high, low, close = self._prior_session_ohlc(df)

            pivot = (high + low + close) / 3.0
            bc = (high + low) / 2.0
            tc = (pivot - bc) + pivot

            cpr_top = np.maximum(tc, bc)
            cpr_bottom = np.minimum(tc, bc)
            with np.errstate(divide="ignore", invalid="ignore"):
                cpr_width_pct = (cpr_top - cpr_bottom) / pivot * 100.0
            is_narrow_cpr = cpr_width_pct < 0.5

            # Camarilla levels from prior session range/close; breakout uses today's close in scanner.
            range_hl = high - low
            cam_h4 = close + (range_hl * 1.1 / 2.0)
            cam_h3 = close + (range_hl * 1.1 / 4.0)
            cam_l3 = close - (range_hl * 1.1 / 4.0)
            cam_l4 = close - (range_hl * 1.1 / 2.0)

            return pd.DataFrame({
                "cpr_pivot": pivot,
                "cpr_tc": cpr_top,
                "cpr_bc": cpr_bottom,
                "cpr_width_pct": cpr_width_pct,
                "is_narrow_cpr": is_narrow_cpr,
                "cam_h3": cam_h3,
                "cam_l3": cam_l3,
                "cam_h4": cam_h4,
                "cam_l4": cam_l4,
            }, index=df.index)
        except Exception as e:
            raise FeatureCalculationError(f"CPRFeature calculation failed: {str(e)}") from e

    def validate(self, series: pd.Series | pd.DataFrame) -> bool:
        if isinstance(series, pd.DataFrame):
            return not series[["cpr_pivot", "cpr_width_pct"]].isnull().any().any()
        return not series.isnull().any()
