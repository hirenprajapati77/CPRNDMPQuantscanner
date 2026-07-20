"""
NDMP OS v6.0 - Feature Store & Plugin Framework Unit Tests
Includes CPR Parity Verification against Ochoa CPR formulas.
"""

import pytest
import pandas as pd
import numpy as np
from ndmp_research.features.cpr_feature import CPRFeature
from ndmp_research.features.vwap_feature import VWAPFeature
from ndmp_research.features.oi_feature import IntradayOIFeature
from ndmp_research.features.rs_feature import RelativeStrengthFeature
from ndmp_research.feature_registry import FeatureRegistry
from ndmp_core.src.exceptions import MissingDependencyError


def test_cpr_feature_ochoa_parity():
    cpr_plugin = CPRFeature()
    df = pd.DataFrame({
        "high": [200.0],
        "low": [190.0],
        "close": [195.0]
    })
    result = cpr_plugin.calculate(df)
    
    # Ochoa Formula Verification:
    # Pivot = (200 + 190 + 195) / 3 = 585 / 3 = 195.0
    # BC = (200 + 190) / 2 = 195.0
    # TC = (195.0 - 195.0) + 195.0 = 195.0
    # CPR Width = |195 - 195| / 195 = 0.0%
    assert result["cpr_pivot"].iloc[0] == pytest.approx(195.0)
    assert result["cpr_tc"].iloc[0] == pytest.approx(195.0)
    assert result["cpr_bc"].iloc[0] == pytest.approx(195.0)
    assert result["cpr_width_pct"].iloc[0] == pytest.approx(0.0)
    assert result["is_narrow_cpr"].iloc[0] == True

    # Camarilla H4/L4 verification:
    # H4 = Close + (High - Low) * 1.1 / 2 = 195 + (10 * 0.55) = 200.5
    assert result["cam_h4"].iloc[0] == pytest.approx(200.5)


def test_vwap_feature():
    vwap_plugin = VWAPFeature()
    df = pd.DataFrame({
        "close": [100.0, 102.0, 105.0, 104.0, 106.0, 110.0],
        "vwap": [99.0, 100.0, 102.0, 103.0, 104.0, 105.0]
    })
    result = vwap_plugin.calculate(df)
    assert "vwap_dist_pct" in result.columns
    assert result["vwap_dist_pct"].iloc[-1] == pytest.approx((110.0 - 105.0) / 105.0 * 100.0)


def test_oi_feature_buildup_classification():
    oi_plugin = IntradayOIFeature()
    df = pd.DataFrame({
        "close": [100.0, 105.0, 108.0, 104.0],
        "open_interest": [1000, 1200, 1100, 1300]
    })
    result = oi_plugin.calculate(df)
    # Row 1: Price Up (+5), OI Up (+200) -> Long Build-up (code 1)
    # Row 2: Price Up (+3), OI Down (-100) -> Short Covering (code 2)
    # Row 3: Price Down (-4), OI Up (+200) -> Short Build-up (code 3)
    assert result["buildup_code"].iloc[1] == 1
    assert result["buildup_code"].iloc[2] == 2
    assert result["buildup_code"].iloc[3] == 3


def test_feature_registry_dynamic_discovery():
    registry = FeatureRegistry(registry_dir="ndmp_research/registry")
    manifests = registry.discover_manifests()
    assert "CPRFeature" in manifests
    assert "VWAPFeature" in manifests
    assert "IntradayOIFeature" in manifests
    assert "RelativeStrengthFeature" in manifests

    registry.register_feature_instance(CPRFeature())
    registry.register_feature_instance(VWAPFeature())

    df = pd.DataFrame({
        "high": [200.0],
        "low": [190.0],
        "close": [195.0],
        "vwap": [192.0]
    })

    out_df = registry.calculate_all(df)
    assert "cpr_pivot" in out_df.columns
    assert "vwap_dist_pct" in out_df.columns


def test_missing_dependency_error():
    registry = FeatureRegistry()
    registry.discover_manifests()
    registry.register_feature_instance(CPRFeature())
    df = pd.DataFrame({
        "close": [195.0]  # Missing 'high' and 'low'
    })
    with pytest.raises(MissingDependencyError):
        registry.calculate_all(df)


def test_duplicate_feature_registration_rejected():
    """Verify that registering duplicate feature name or ID raises an NDMPError."""
    from ndmp_core.src.exceptions import NDMPError
    registry = FeatureRegistry()
    registry.discover_manifests()
    registry.register_feature_instance(CPRFeature())
    
    # Duplicate Name
    with pytest.raises(NDMPError, match="Feature name duplicate registration"):
        registry.register_feature_instance(CPRFeature())


def test_manifest_version_mismatch_rejected():
    """Verify that version mismatch between manifest and plugin raises an NDMPError."""
    from ndmp_core.src.exceptions import NDMPError
    registry = FeatureRegistry()
    registry.discover_manifests()
    
    # Mock a mismatching plugin
    class BadVersionCPR(CPRFeature):
        def version(self) -> str:
            return "2.0.0"  # manifest expects 1.0.0
            
    with pytest.raises(NDMPError, match="Version mismatch"):
        registry.register_feature_instance(BadVersionCPR())


def test_circular_dependency_detection():
    """Verify that circular dependency graph cycle detection triggers NDMPError."""
    from ndmp_core.src.exceptions import NDMPError
    registry = FeatureRegistry()
    
    # Setup mock manifests in registry memory
    registry.manifests["FeatureA"] = {"id": "FEAT_A", "name": "FeatureA", "version": "1.0.0", "dependencies": ["FeatureB"]}
    registry.manifests["FeatureB"] = {"id": "FEAT_B", "name": "FeatureB", "version": "1.0.0", "dependencies": ["FeatureA"]}

    # Create dummy plugins with cross dependencies
    class FeatureA(CPRFeature):
        def metadata(self): return {"id": "FEAT_A", "name": "FeatureA"}
        def version(self): return "1.0.0"
        def dependencies(self): return ["FeatureB"]
        
    class FeatureB(CPRFeature):
        def metadata(self): return {"id": "FEAT_B", "name": "FeatureB"}
        def version(self): return "1.0.0"
        def dependencies(self): return ["FeatureA"]

    registry.register_feature_instance(FeatureA())
    with pytest.raises(NDMPError, match="Circular dependency detected"):
        registry.register_feature_instance(FeatureB())


def test_cpr_zero_range_candle():
    """Verify CPR Feature handles zero range candles (High == Low) without divide-by-zero errors."""
    cpr_plugin = CPRFeature()
    df = pd.DataFrame({
        "high": [100.0, 100.0],
        "low": [100.0, 100.0],
        "close": [100.0, 100.0]
    })
    res = cpr_plugin.calculate(df)
    assert res["cpr_width_pct"].iloc[-1] == 0.0
    assert res["cam_h4"].iloc[-1] == 100.0
    assert res["cam_l4"].iloc[-1] == 100.0


def test_oi_buildup_neutral_quadrant():
    """Verify that flat price or flat Open Interest changes are classified as Neutral (0)."""
    oi_plugin = IntradayOIFeature()
    # Cases with flat price or flat Open Interest
    df = pd.DataFrame({
        "close": [100.0, 100.0, 105.0, 105.0],
        "open_interest": [1000, 1200, 1200, 1000]
    })
    res = oi_plugin.calculate(df)
    
    # Row 1: Price flat (0), OI up (+200) -> Neutral (0)
    # Row 2: Price up (+5), OI flat (0) -> Neutral (0)
    # Row 3: Price flat (0), OI down (-200) -> Neutral (0)
    assert res["buildup_code"].iloc[1] == 0
    assert res["buildup_code"].iloc[2] == 0
    assert res["buildup_code"].iloc[3] == 0


def test_benchmark_reproducibility():
    """Verify that running the benchmark suite with minimal iterations completes successfully."""
    from benchmarks.benchmark_scanner import run_benchmark_suite
    # Run with 2 iterations and 1 warmup to verify execution path works without errors
    run_benchmark_suite(num_iterations=2, warmups=1)



