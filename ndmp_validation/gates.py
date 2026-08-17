"""
NDMP OS v6.0 - 5 Quantitative Governance Promotion Gates
Defines the strict quantitative thresholds required for model/feature promotion.
"""

from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from ndmp_core.src.config import GovernanceConfig, DEFAULT_CONFIG


class GovernanceGateResult(BaseModel):
    """Result of single Governance Gate inspection."""
    gate_id: str
    gate_name: str
    target_threshold: str
    realized_value: float
    passed: bool
    description: str


class GovernanceGateSuiteResult(BaseModel):
    """Complete Suite Result across all 5 Gates."""
    validation_id: str
    timestamp_utc: str
    dataset_version: str
    git_commit: str
    overall_status: str  # PASS | FAIL
    gate_results: List[GovernanceGateResult]


class GovernanceGateChecker:
    """Evaluates candidate performance against the 5 Production Promotion Gates."""

    def __init__(self, config: Optional[GovernanceConfig] = None):
        cfg = config or DEFAULT_CONFIG.governance
        self.GATE_1_MIN_PROFIT_FACTOR = cfg.min_oos_profit_factor
        self.GATE_2_MIN_DEFLATED_SHARPE = cfg.min_deflated_sharpe
        self.GATE_3_MAX_PBO_PERCENT = cfg.max_pbo_percent
        self.GATE_4_MAX_SHAP_STABILITY_VAR = cfg.max_shap_stability_var
        self.GATE_5_MIN_MARGINAL_EV_GAIN = cfg.min_marginal_ev_gain
        self._friction_pct_label = cfg.frictional_cost_percent

    def evaluate_all_gates(
        self,
        validation_id: str,
        dataset_version: str,
        git_commit: str,
        realized_pf: float,
        realized_dsr: float,
        realized_pbo_pct: float,
        realized_shap_var: float,
        realized_marginal_ev: float
    ) -> GovernanceGateSuiteResult:
        """Evaluate candidate results against all 5 gates."""

        gate1 = GovernanceGateResult(
            gate_id="GATE_001",
            gate_name="Out-of-Sample Profit Factor",
            target_threshold=f">= {self.GATE_1_MIN_PROFIT_FACTOR:.2f} (post {self._friction_pct_label}% friction)",
            realized_value=round(realized_pf, 2),
            passed=realized_pf >= self.GATE_1_MIN_PROFIT_FACTOR,
            description="Gross Profits / Gross Losses ratio in out-of-sample walk-forward test."
        )

        gate2 = GovernanceGateResult(
            gate_id="GATE_002",
            gate_name="Deflated Sharpe Ratio (DSR)",
            target_threshold=f">= {self.GATE_2_MIN_DEFLATED_SHARPE:.2f}",
            realized_value=round(realized_dsr, 2),
            passed=realized_dsr >= self.GATE_2_MIN_DEFLATED_SHARPE,
            description="Sharpe ratio adjusted for multiple testing, skewness, and kurtosis."
        )

        gate3 = GovernanceGateResult(
            gate_id="GATE_003",
            gate_name="Probability of Overfitting (PBO)",
            target_threshold=f"<= {self.GATE_3_MAX_PBO_PERCENT:.1f}%",
            realized_value=round(realized_pbo_pct, 2),
            passed=realized_pbo_pct <= self.GATE_3_MAX_PBO_PERCENT,
            description="Percentage of CPCV paths where in-sample optimal model underperforms out-of-sample median."
        )

        gate4 = GovernanceGateResult(
            gate_id="GATE_004",
            gate_name="SHAP Stability Rank Variance",
            target_threshold=f"<= {self.GATE_4_MAX_SHAP_STABILITY_VAR:.2f}",
            realized_value=round(realized_shap_var, 2),
            passed=realized_shap_var <= self.GATE_4_MAX_SHAP_STABILITY_VAR,
            description="Variance of feature importance rank across rolling monthly windows."
        )

        gate5 = GovernanceGateResult(
            gate_id="GATE_005",
            gate_name="Marginal Expected Value Gain",
            target_threshold=f">= +{self.GATE_5_MIN_MARGINAL_EV_GAIN:.2f}% per trade",
            realized_value=round(realized_marginal_ev, 2),
            passed=realized_marginal_ev >= self.GATE_5_MIN_MARGINAL_EV_GAIN,
            description="Net improvement in expected return per trade over baseline CPR scanner."
        )

        gates = [gate1, gate2, gate3, gate4, gate5]
        all_passed = all(g.passed for g in gates)

        return GovernanceGateSuiteResult(
            validation_id=validation_id,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            dataset_version=dataset_version,
            git_commit=git_commit,
            overall_status="PASS" if all_passed else "FAIL",
            gate_results=gates
        )
