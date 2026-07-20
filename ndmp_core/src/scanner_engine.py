"""
NDMP OS v6.0 - Deterministic Scanner Engine
Computes features across stock universe at 3:20 PM IST and outputs Signal Objects.
"""

import pandas as pd
from pydantic import BaseModel, Field
from typing import Dict, List, Any
from ndmp_research.feature_registry import FeatureRegistry
from ndmp_research.features.cpr_feature import CPRFeature
from ndmp_research.features.vwap_feature import VWAPFeature
from ndmp_research.features.oi_feature import IntradayOIFeature
from ndmp_research.features.rs_feature import RelativeStrengthFeature
from ndmp_core.src.exceptions import DataValidationError


class StockSignals(BaseModel):
    """Deterministic Signal Object per Stock."""
    symbol: str
    timestamp: str
    is_narrow_cpr: bool
    cpr_width_pct: float
    vwap_dist_pct: float
    buildup_code: int  # 1: Long Build-up, 2: Short Cover, 3: Short Build-up, 4: Long Unwind
    mansfield_rs: float
    close: float
    cam_h4: float
    cam_l4: float


class ScannerEngine:
    """Deterministic Scanner Engine for NDMP OS."""

    def __init__(self, registry: FeatureRegistry | None = None):
        if registry is None:
            self.registry = FeatureRegistry()
            self.registry.discover_manifests()
            self.registry.register_feature_instance(CPRFeature())
            self.registry.register_feature_instance(VWAPFeature())
            self.registry.register_feature_instance(IntradayOIFeature())
            self.registry.register_feature_instance(RelativeStrengthFeature())
        else:
            self.registry = registry

    def scan_symbol(self, symbol: str, df: pd.DataFrame) -> StockSignals:
        """Compute all features and generate a StockSignals object."""
        if df.empty:
            raise DataValidationError(f"Cannot scan symbol '{symbol}': input DataFrame is empty.")

        feat_df = self.registry.calculate_all(df)
        if feat_df.empty:
            raise DataValidationError(f"Cannot scan symbol '{symbol}': calculated features DataFrame is empty.")

        last_row = feat_df.iloc[-1]
        raw_last = df.iloc[-1]

        # Check for NaN values in key columns to prevent invalid metrics propagation
        key_cols = ["is_narrow_cpr", "cpr_width_pct", "vwap_dist_pct", "buildup_code", "mansfield_rs", "cam_h4", "cam_l4"]
        for col in key_cols:
            if pd.isna(last_row[col]):
                raise DataValidationError(f"NaN value detected in feature '{col}' for symbol '{symbol}'.")

        return StockSignals(
            symbol=symbol,
            timestamp=str(raw_last["timestamp"]),
            is_narrow_cpr=bool(last_row["is_narrow_cpr"]),
            cpr_width_pct=float(last_row["cpr_width_pct"]),
            vwap_dist_pct=float(last_row["vwap_dist_pct"]),
            buildup_code=int(last_row["buildup_code"]),
            mansfield_rs=float(last_row["mansfield_rs"]),
            close=float(raw_last["close"]),
            cam_h4=float(last_row["cam_h4"]),
            cam_l4=float(last_row["cam_l4"])
        )
