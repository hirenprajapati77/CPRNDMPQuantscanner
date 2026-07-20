"""
NDMP OS v6.0 - RelativeStrengthFeature Plugin
Calculates Mansfield Relative Strength vs Benchmark Nifty 50 Index.
"""

from typing import Dict, Any, List
import pandas as pd
import numpy as np
from ndmp_research.features.base_feature import BaseFeature
from ndmp_core.src.exceptions import MissingDependencyError, FeatureCalculationError


class RelativeStrengthFeature(BaseFeature):
    """Mansfield Relative Strength vs Benchmark Plugin."""

    def __init__(self, manifest_path: str | None = None):
        super().__init__(feature_id="FEAT_004", manifest_path=manifest_path)

    def dependencies(self) -> List[str]:
        return ["close", "benchmark_close"]

    def version(self) -> str:
        return "1.0.0"

    def metadata(self) -> Dict[str, Any]:
        return {
            "id": self.feature_id,
            "name": "RelativeStrengthFeature",
            "version": self.version(),
            "category": "RelativeMomentum",
            "dependencies": self.dependencies()
        }

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        for dep in self.dependencies():
            if dep not in df.columns:
                raise MissingDependencyError(f"RelativeStrengthFeature missing required column: {dep}")

        try:
            stock_close = df["close"]
            nifty_close = df["benchmark_close"]
            rel_ratio = stock_close / nifty_close
            period = 14
            sma_rel_ratio = rel_ratio.rolling(window=period, min_periods=1).mean()
            mansfield_rs = ((rel_ratio / sma_rel_ratio) - 1.0) * 100.0

            return pd.DataFrame({
                "mansfield_rs": mansfield_rs.fillna(0.0)
            }, index=df.index)
        except Exception as e:
            raise FeatureCalculationError(f"RelativeStrengthFeature calculation failed: {str(e)}") from e

    def validate(self, series: pd.Series | pd.DataFrame) -> bool:
        if isinstance(series, pd.DataFrame):
            return not series["mansfield_rs"].isnull().any()
        return not series.isnull().any()
