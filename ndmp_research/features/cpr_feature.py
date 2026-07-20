"""
NDMP OS v6.0 - CPRFeature Plugin
Calculates Frank Ochoa Central Pivot Range (Pivot, TC, BC, CPR Width %, Narrow CPR flag) & Camarilla levels.
"""

from typing import Dict, Any, List
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

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate CPR & Camarilla indicators.
        Returns DataFrame with ['cpr_pivot', 'cpr_tc', 'cpr_bc', 'cpr_width_pct', 'is_narrow_cpr', 'cam_h3', 'cam_l3', 'cam_h4', 'cam_l4'].
        """
        for dep in self.dependencies():
            if dep not in df.columns:
                raise MissingDependencyError(f"CPRFeature missing required column: {dep}")

        try:
            high = df["high"].values
            low = df["low"].values
            close = df["close"].values

            # Classic Frank Ochoa CPR Calculations
            pivot = (high + low + close) / 3.0
            bc = (high + low) / 2.0
            tc = (pivot - bc) + pivot

            # Handle TC/BC ordering convention
            cpr_top = np.maximum(tc, bc)
            cpr_bottom = np.minimum(tc, bc)
            cpr_width_pct = (cpr_top - cpr_bottom) / pivot * 100.0
            is_narrow_cpr = cpr_width_pct < 0.5  # < 0.5% threshold

            # Camarilla Equation
            range_hl = high - low
            cam_h4 = close + (range_hl * 1.1 / 2.0)
            cam_h3 = close + (range_hl * 1.1 / 4.0)
            cam_l3 = close - (range_hl * 1.1 / 4.0)
            cam_l4 = close - (range_hl * 1.1 / 2.0)

            result = pd.DataFrame({
                "cpr_pivot": pivot,
                "cpr_tc": cpr_top,
                "cpr_bc": cpr_bottom,
                "cpr_width_pct": cpr_width_pct,
                "is_narrow_cpr": is_narrow_cpr,
                "cam_h3": cam_h3,
                "cam_l3": cam_l3,
                "cam_h4": cam_h4,
                "cam_l4": cam_l4
            }, index=df.index)

            return result
        except Exception as e:
            raise FeatureCalculationError(f"CPRFeature calculation failed: {str(e)}") from e

    def validate(self, series: pd.Series | pd.DataFrame) -> bool:
        if isinstance(series, pd.DataFrame):
            return not series[["cpr_pivot", "cpr_width_pct"]].isnull().any().any()
        return not series.isnull().any()
