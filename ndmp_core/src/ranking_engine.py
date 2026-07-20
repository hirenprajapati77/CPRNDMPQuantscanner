"""
NDMP OS v6.0 - Deterministic Ranking Engine
Independent module scoring and ranking StockSignals candidates into a ranked list.
"""

from pydantic import BaseModel
from typing import List, Dict, Any
from ndmp_core.src.scanner_engine import StockSignals
from ndmp_core.src.explainability import ExplainabilityEngine


class RankedCandidate(BaseModel):
    """Ranked Stock Candidate Record."""
    rank: int
    symbol: str
    score: float
    signals: StockSignals
    reasons: List[str]


class RankingEngine:
    """Independent Ranking Engine for NDMP OS."""

    @staticmethod
    def calculate_score(signals: StockSignals) -> float:
        """Calculate deterministic composite score (0-100 scale)."""
        score = 50.0

        if signals.is_narrow_cpr:
            score += 20.0

        if signals.buildup_code == 1:  # Long Build-up
            score += 15.0
        elif signals.buildup_code == 2:  # Short Covering
            score += 8.0
        elif signals.buildup_code == 3:  # Short Build-up
            score -= 15.0

        if signals.vwap_dist_pct > 0.0:
            score += 7.0

        if signals.mansfield_rs > 0.0:
            score += min(10.0, signals.mansfield_rs * 2.0)

        if signals.close >= signals.cam_h4:
            score += 8.0

        return round(min(100.0, max(0.0, score)), 2)

    def rank_candidates(self, signal_list: List[StockSignals]) -> List[RankedCandidate]:
        """Rank a list of StockSignals objects by score descending."""
        scored_candidates = []
        for sig in signal_list:
            score = self.calculate_score(sig)
            reasons = ExplainabilityEngine.explain(sig)
            scored_candidates.append((score, sig, reasons))

        # Sort by score descending, then symbol ascending
        scored_candidates.sort(key=lambda x: (-x[0], x[1].symbol))

        ranked_list = []
        for idx, (score, sig, reasons) in enumerate(scored_candidates, start=1):
            ranked_list.append(
                RankedCandidate(
                    rank=idx,
                    symbol=sig.symbol,
                    score=score,
                    signals=sig,
                    reasons=reasons
                )
            )
        return ranked_list
