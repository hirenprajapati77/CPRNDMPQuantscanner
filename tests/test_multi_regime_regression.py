"""
NDMP OS v6.0 - Multi-Regime Regression Benchmark Suite
Verifies deterministic scanner performance across 3 distinct market regimes:
1. Normal Market Day (2025-07-18)
2. High-Volatility Shock Market (VIX > 22)
3. Major Event Day (Union Budget / Election Results)
"""

import os
import json
import pytest
import numpy as np
import pandas as pd
from ndmp_core.src.scanner_engine import ScannerEngine
from ndmp_core.src.ranking_engine import RankingEngine
from ndmp_validation.validation_engine import ValidationEngine
from ndmp_validation.dashboard import GovernanceDashboard


def test_normal_market_regime():
    """Scenario 1: Normal Market Session (2025-07-18)."""
    scanner = ScannerEngine()
    ranker = RankingEngine()
    dates = pd.date_range("2025-07-18 15:15:00", periods=5, freq="1min")

    df_bel = pd.DataFrame({
        "timestamp": dates, "symbol": ["BEL"] * 5,
        "open": [198.0, 198.5, 199.0, 199.2, 199.5], "high": [200.0] * 5, "low": [199.5] * 5,
        "close": [198.5, 199.0, 199.2, 199.5, 199.8], "volume": [10000] * 5,
        "open_interest": [50000, 51000, 52000, 53000, 54000], "vwap": [198.5] * 5,
        "benchmark_close": [24000.0] * 5
    })
    sig = scanner.scan_symbol("BEL", df_bel)
    ranked = ranker.rank_candidates([sig])
    assert ranked[0].symbol == "BEL"
    assert ranked[0].score >= 90.0


def test_high_volatility_shock_regime():
    """Scenario 2: High Volatility Shock Market (VIX > 22). Wide price swings + Short Build-up."""
    scanner = ScannerEngine()
    ranker = RankingEngine()
    dates = pd.date_range("2026-03-15 15:15:00", periods=5, freq="1min")

    # High Volatility stock with large range (High=150, Low=120 -> CPR Width = 23%) & Price Down (-5), OI Up (+5000)
    df_shock = pd.DataFrame({
        "timestamp": dates, "symbol": ["SHOCK_STOCK"] * 5,
        "open": [140.0, 130.0, 125.0, 122.0, 120.0], "high": [150.0] * 5, "low": [120.0] * 5,
        "close": [130.0, 125.0, 122.0, 120.0, 115.0], "volume": [100000] * 5,
        "open_interest": [80000, 85000, 90000, 95000, 100000], "vwap": [135.0] * 5,
        "benchmark_close": [22000.0] * 5
    })
    sig = scanner.scan_symbol("SHOCK_STOCK", df_shock)
    ranked = ranker.rank_candidates([sig])
    # Short Build-up & Below VWAP -> Score < 40.0
    assert ranked[0].signals.is_narrow_cpr is False
    assert ranked[0].signals.buildup_code == 3  # Short Build-up
    assert ranked[0].score < 40.0


def test_major_event_day_regime():
    """Scenario 3: Major Event Day (Budget / Election Day). Strong momentum breakout."""
    scanner = ScannerEngine()
    ranker = RankingEngine()
    dates = pd.date_range("2026-02-01 15:15:00", periods=5, freq="1min")

    df_event = pd.DataFrame({
        "timestamp": dates, "symbol": ["EVENT_WINNER"] * 5,
        "open": [496.0, 500.0, 505.0, 510.0, 514.0], "high": [500.0, 502.0, 505.0, 510.0, 530.0], "low": [495.0, 498.0, 500.0, 505.0, 510.0],
        "close": [498.0, 502.0, 508.0, 515.0, 528.0], "volume": [50000] * 5,
        "open_interest": [40000, 42000, 44000, 46000, 48000], "vwap": [502.0] * 5,
        "benchmark_close": [24500.0] * 5
    })
    sig = scanner.scan_symbol("EVENT_WINNER", df_event)
    ranked = ranker.rank_candidates([sig])
    assert ranked[0].score >= 70.0


def test_governance_validation_engine_pass():
    """Verify independent validation engine passes strong candidate returns."""
    engine = ValidationEngine()

    # Generate 100 out-of-sample trade returns (mean +1.2%, std 1.5%)
    np.random.seed(42)
    candidate_returns = np.random.normal(loc=0.012, scale=0.015, size=100)
    baseline_returns = np.random.normal(loc=0.005, scale=0.015, size=100)

    suite_result = engine.evaluate_candidate(
        validation_id="VAL-20260720-001",
        dataset_version="NSE_FO_5YR_V1.2",
        git_commit="a1b2c3d4e5f67890",
        candidate_returns=candidate_returns,
        baseline_returns=baseline_returns,
        shap_stability_var=0.85
    )

    # Render dashboard
    dashboard_text = GovernanceDashboard.render(suite_result)
    assert suite_result.overall_status == "PASS"
    assert "PROMOTED" in dashboard_text


def test_release_promotion_packet_compilation(tmp_path):
    """Verify that ReleaseManager successfully compiles and archives the Release Promotion Packet."""
    from ndmp_validation.release_manager import ReleaseManager
    from ndmp_validation.validation_engine import ValidationEngine
    import numpy as np

    engine = ValidationEngine()
    np.random.seed(42)
    candidate_returns = np.random.normal(loc=0.012, scale=0.015, size=100)
    baseline_returns = np.random.normal(loc=0.005, scale=0.015, size=100)

    suite_result = engine.evaluate_candidate(
        validation_id="VAL-20260720-001",
        dataset_version="NSE_FO_5YR_V1.2",
        git_commit="a1b2c3d4e5f67890",
        candidate_returns=candidate_returns,
        baseline_returns=baseline_returns,
        shap_stability_var=0.85
    )

    manager = ReleaseManager(release_dir=str(tmp_path))
    packet_path = manager.compile_release_packet(
        gate_results=suite_result,
        benchmark_mean_ms=893.4,
        benchmark_p95_ms=995.2,
        peak_memory_mb=0.73
    )

    assert os.path.exists(packet_path)
    with open(packet_path, "r") as f:
        data = json.load(f)
    assert data["release_id"].startswith("REL-")
    assert data["governance_gates"]["overall_status"] == "PASS"


def test_gates_timestamp_utc_correctness():
    """Verify that GovernanceGateSuiteResult includes a valid ISO UTC timestamp, not dataset_version."""
    from ndmp_validation.validation_engine import ValidationEngine
    import numpy as np

    engine = ValidationEngine()
    candidate_returns = np.array([0.01, 0.02, -0.01])
    baseline_returns = np.array([0.005, 0.01, -0.005])

    suite_result = engine.evaluate_candidate(
        validation_id="VAL-TEST",
        dataset_version="DATA_VERSION_123",
        git_commit="COMMIT_123",
        candidate_returns=candidate_returns,
        baseline_returns=baseline_returns
    )

    # Must be valid ISO timestamp, not DATA_VERSION_123
    assert suite_result.timestamp_utc != "DATA_VERSION_123"
    assert "T" in suite_result.timestamp_utc  # ISO format check


def test_weekly_review_generator_execution(tmp_path):
    """Verify weekly review generator executes without NameError and creates output file."""
    from ndmp_validation.weekly_review_generator import WeeklyReviewGenerator
    generator = WeeklyReviewGenerator(
        journal_dir=str(tmp_path),
        output_dir=str(tmp_path)
    )
    report_path = generator.generate_report(week_num=1)
    assert os.path.exists(report_path)


