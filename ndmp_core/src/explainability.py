"""
NDMP OS v6.0 - Signal Explainability Engine
Generates human-readable explanations for scanner recommendations.
"""

from typing import List
from ndmp_core.src.scanner_engine import StockSignals


class ExplainabilityEngine:
    """Generates human-readable explanations for technical & flow signals."""

    @staticmethod
    def explain(signals: StockSignals) -> List[str]:
        reasons: List[str] = []

        if signals.is_narrow_cpr:
            reasons.append(f"✔ Narrow CPR (Width: {signals.cpr_width_pct:.2f}%)")

        if signals.buildup_code == 1:
            reasons.append("✔ Long Build-up (Price Up + OI Accumulation)")
        elif signals.buildup_code == 2:
            reasons.append("✔ Short Covering (Price Up + OI Reduction)")
        elif signals.buildup_code == 3:
            reasons.append("⚠ Short Build-up (Price Down + OI Accumulation)")
        elif signals.buildup_code == 4:
            reasons.append("⚠ Long Unwinding (Price Down + OI Reduction)")

        if signals.vwap_dist_pct > 0.0:
            reasons.append(f"✔ Above VWAP (+{signals.vwap_dist_pct:.2f}%)")
        else:
            reasons.append(f"⚠ Below VWAP ({signals.vwap_dist_pct:.2f}%)")

        if signals.mansfield_rs > 0.0:
            reasons.append(f"✔ Outperforming Nifty 50 (Mansfield RS: +{signals.mansfield_rs:.2f})")

        if signals.close >= signals.cam_h4:
            reasons.append("⚡ Breakout Above Camarilla H4")

        return reasons
