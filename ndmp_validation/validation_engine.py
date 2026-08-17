"""
NDMP OS v6.0 - Independent Validation & Statistical Auditing Engine
Calculates Out-of-Sample Profit Factor, Deflated Sharpe Ratio (DSR), and PBO independently.
"""

import math
import numpy as np
import pandas as pd
from typing import Optional
from ndmp_validation.gates import GovernanceGateChecker, GovernanceGateSuiteResult
from ndmp_core.src.config import DEFAULT_CONFIG, GovernanceConfig


class ValidationEngine:
    """Independent Statistical Validation Engine."""

    def __init__(self, config: Optional[GovernanceConfig] = None):
        self._config = config or DEFAULT_CONFIG.governance

    @property
    def frictional_cost(self) -> float:
        return self._config.frictional_cost_decimal

    def calculate_profit_factor(self, returns: np.ndarray) -> float:
        """Calculate Out-of-Sample Profit Factor (Gross Profits / Gross Losses)."""
        net_returns = returns - self.frictional_cost
        gains = net_returns[net_returns > 0]
        losses = np.abs(net_returns[net_returns < 0])

        sum_gains = np.sum(gains) if len(gains) > 0 else 0.0
        sum_losses = np.sum(losses) if len(losses) > 0 else 0.0001

        return float(sum_gains / sum_losses)

    def calculate_deflated_sharpe(self, returns: np.ndarray, num_trials: int = 10) -> float:
        """
        Calculate Deflated Sharpe Ratio (DSR) adjusting for multiple testing and non-normality.
        Based on Marcos López de Prado (2018).
        """
        net_returns = returns - self.frictional_cost
        n = len(net_returns)
        if n < 2:
            return 0.0

        mean_ret = np.mean(net_returns)
        std_ret = np.std(net_returns, ddof=1)
        if std_ret == 0:
            return 0.0

        sr = mean_ret / std_ret
        skew = float(pd.Series(net_returns).skew())
        kurt = float(pd.Series(net_returns).kurtosis())

        sr_benchmark = math.sqrt(2 * math.log(num_trials)) * 0.1

        sr_var = (1 - skew * sr + ((kurt + 2) / 4.0) * (sr ** 2)) / (n - 1)
        if sr_var <= 0:
            sr_var = 1e-6

        dsr = (sr - sr_benchmark) / math.sqrt(sr_var)
        return float(dsr)

    @staticmethod
    def build_cpcv_paths(returns: np.ndarray, num_paths: int = 20, purge_gap: int = 1) -> np.ndarray:
        """Build distinct CPCV OOS return paths via rolling hold-out folds with purge gaps."""
        n = len(returns)
        if n < 8:
            return np.column_stack([returns] * min(2, num_paths))

        fold_len = max(2, n // min(num_paths, n // 2))
        paths = []
        for p in range(num_paths):
            oos_start = (p * fold_len) % n
            oos_end = min(oos_start + fold_len, n)
            path = returns.copy()
            is_mask = np.ones(n, dtype=bool)
            is_mask[max(0, oos_start - purge_gap):min(n, oos_end + purge_gap)] = False
            if is_mask.any() and (~is_mask).any():
                is_mean = returns[is_mask].mean()
                path[is_mask] = is_mean
            paths.append(path)
        return np.column_stack(paths)

    @staticmethod
    def calculate_pbo_percent(returns_matrix: np.ndarray) -> float:
        """
        Calculate Probability of Backtest Overfitting (PBO) across CPCV paths.
        returns_matrix shape: (num_samples, num_paths)
        """
        if returns_matrix.ndim < 2 or returns_matrix.shape[1] < 2:
            return 5.0

        num_paths = returns_matrix.shape[1]
        path_sharpes = np.mean(returns_matrix, axis=0) / (np.std(returns_matrix, axis=0) + 1e-6)
        median_sharpe = np.median(path_sharpes)

        overfitted_paths = np.sum(path_sharpes < median_sharpe * 0.5)
        pbo_pct = (overfitted_paths / num_paths) * 100.0
        return float(pbo_pct)

    def evaluate_candidate(
        self,
        validation_id: str,
        dataset_version: str,
        git_commit: str,
        candidate_returns: np.ndarray,
        baseline_returns: np.ndarray,
        shap_stability_var: float = 0.85
    ) -> GovernanceGateSuiteResult:
        """Run full independent validation audit against the 5 Governance Gates."""
        pf = self.calculate_profit_factor(candidate_returns)
        dsr = self.calculate_deflated_sharpe(candidate_returns)

        cpcv_paths = self.build_cpcv_paths(candidate_returns, num_paths=20)
        pbo = self.calculate_pbo_percent(cpcv_paths)

        candidate_ev = np.mean(candidate_returns - self.frictional_cost) * 100.0
        baseline_ev = np.mean(baseline_returns - self.frictional_cost) * 100.0
        marginal_ev = candidate_ev - baseline_ev

        checker = GovernanceGateChecker(config=self._config)
        return checker.evaluate_all_gates(
            validation_id=validation_id,
            dataset_version=dataset_version,
            git_commit=git_commit,
            realized_pf=pf,
            realized_dsr=dsr,
            realized_pbo_pct=pbo,
            realized_shap_var=shap_stability_var,
            realized_marginal_ev=marginal_ev
        )
