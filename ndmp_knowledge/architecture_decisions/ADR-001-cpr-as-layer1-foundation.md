# ADR-001: Retention of CPR as Layer 1 Foundation

- **Status**: Accepted
- **Date**: 2026-07-20
- **Authors**: Quantitative Research & Engineering Team

## Context & Problem Statement

NDMP OS v6.0 aims to detect overnight momentum opportunities in NSE F&O stocks. A foundational technical price geometry framework is required to ground higher-dimensional features (OI velocity, volume profile, microstructure, relative strength).

## Decision

Central Pivot Range (CPR) technical geometry (Pivot, Top Central TC, Bottom Central BC) along with Camarilla levels (H3/L3, H4/L4) will serve as the mandatory Layer 1 price structural foundation.

## Rationale

1. **Proven Production Baseline**: CPR demonstrates a strong empirical baseline win rate (58–62%) in historical backtests.
2. **Computational Overhead**: $O(1)$ calculation complexity per stock, completing in $< 0.1 \text{ ms}$.
3. **Explainability**: High institutional and technical trader adoption makes CPR zones self-fulfilling liquidity pools.

## Consequences & Rejections

- **Rejected Alternative 1: VWAP-Only Baseline**. Rejected due to high whipsaw frequency during range-bound regimes.
- **Rejected Alternative 2: End-to-End Neural Network**. Rejected due to black-box lack of interpretability and high overfitting risk ($PBO > 40\%$).
