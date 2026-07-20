# ADR-002: BaseFeature Immutable Contract & Data Schemas

- **Status**: Accepted
- **Date**: 2026-07-20
- **Authors**: Quantitative Engineering Team

## Context & Problem Statement

To prevent tight coupling and feature spaghetti code as NDMP OS expands to dozens of quantitative features, a standardized plugin abstraction and data schema contract is needed.

## Decision

1. All feature plugins in `ndmp-research/features/` must inherit from the abstract class `BaseFeature` located in `ndmp-research/features/base_feature.py`.
2. Every feature plugin MUST implement:
   - `calculate(df: pd.DataFrame) -> pd.Series`
   - `validate(series: pd.Series) -> bool`
   - `metadata() -> Dict[str, Any]`
   - `version() -> str`
   - `dependencies() -> List[str]`
3. Features are declared via `feature.yaml` manifests. No hardcoded feature parameters in production code.

## Rationale

- Ensures strict zero look-ahead bias validation at runtime.
- Allows seamless plug-and-play feature additions without modifying core execution code (`ndmp-core`).
- Guarantees 100% auditability and reproducibility.
