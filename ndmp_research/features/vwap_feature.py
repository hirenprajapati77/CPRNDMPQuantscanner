"""
NDMP OS v6.0 - VWAPFeature Plugin
Calculates VWAP distance percentage and VWAP slope.
"""

from typing import Dict, Any, List
import pandas as pd
import numpy as np
from ndmp_research.features.base_feature import BaseFeature
from ndmp_core.src.exceptions import MissingDependencyError, FeatureCalculationError


class VWAPFeature(BaseFeature):
    """VWAP Distance & Microstructure Slope Feature Plugin."""

    def __init__(self, manifest_path: str | None = None):
        super().__init__(feature_id="FEAT_002", manifest_path=manifest_path)

    def dependencies(self) -> List[str]:
        return ["close", "vwap"]

    def version(self) -> str:
        return "1.0.0"

    def metadata(self) -> Dict[str, Any]:
        return {
            "id": self.feature_id,
            "name": "VWAPFeature",
            "version": self.version(),
            "category": "Microstructure",
            "dependencies": self.dependencies()
        }

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        for dep in self.dependencies():
            if dep not in df.columns:
                raise MissingDependencyError(f"VWAPFeature missing required column: {dep}")

        try:
            close = df["close"]
            vwap = df["vwap"]
            vwap_dist_pct = (close - vwap) / vwap * 100.0
            vwap_slope = vwap.diff(5) / vwap.shift(5) * 100.0

            return pd.DataFrame({
                "vwap_dist_pct": vwap_dist_pct,
                "vwap_slope_5p": vwap_slope.fillna(0.0)
            }, index=df.index)
        except Exception as e:
            raise FeatureCalculationError(f"VWAPFeature calculation failed: {str(e)}") from e

    def validate(self, series: pd.Series | pd.DataFrame) -> bool:
        if isinstance(series, pd.DataFrame):
            return not series["vwap_dist_pct"].isnull().any()
        return not series.isnull().any()
