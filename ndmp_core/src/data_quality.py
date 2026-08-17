"""
NDMP OS v6.0 - Data Quality Engine & Dataset Auditor
Calculates Data Quality Scores (0-100) and produces audit reports for incoming feeds.
"""

import hashlib
import io
from datetime import date

import pandas as pd
from pydantic import BaseModel, Field

from .exceptions import DataValidationError
from .trading_calendar import NSETradingCalendar


class DataQualityReport(BaseModel):
    """Dataset Quality Inspection Summary Report."""
    dataset_name: str
    total_records: int
    unique_symbols: int
    missing_values_count: int
    duplicate_rows_count: int
    completeness_percent: float = Field(..., ge=0.0, le=100.0)
    schema_passed: bool
    calendar_passed: bool
    oi_integrity_passed: bool = True
    checksum_sha256: str
    quality_score: float = Field(..., ge=0.0, le=100.0)
    status: str  # ACCEPTED | REJECTED


class DataQualityAuditor:
    """Audits pandas DataFrames against quality standards and calculates Quality Score."""

    QUALITY_THRESHOLD: float = 95.0

    def __init__(self, calendar: NSETradingCalendar | None = None):
        self.calendar = calendar or NSETradingCalendar()

    @staticmethod
    def compute_sha256(df: pd.DataFrame) -> str:
        """Compute deterministic SHA-256 hash via canonical parquet serialization."""
        canonical = df.sort_index(axis=1)
        buf = io.BytesIO()
        canonical.to_parquet(buf, index=False)
        return hashlib.sha256(buf.getvalue()).hexdigest()

    @staticmethod
    def _check_oi_integrity(df: pd.DataFrame) -> bool:
        """Reject constant or all-NaN open_interest (fake/missing futures OI)."""
        if "open_interest" not in df.columns:
            return True
        oi = df["open_interest"]
        if oi.isna().all():
            return False
        if oi.nunique(dropna=True) <= 1:
            return False
        if pd.isna(oi.iloc[-1]):
            return False
        return True

    @staticmethod
    def _check_calendar(df: pd.DataFrame, calendar: NSETradingCalendar) -> bool:
        if "timestamp" not in df.columns or df.empty:
            return True
        last_ts = pd.to_datetime(df["timestamp"].iloc[-1])
        return calendar.is_trading_day(last_ts.date())

    def audit_dataframe(
        self,
        df: pd.DataFrame,
        dataset_name: str,
        expected_columns: list[str]
    ) -> DataQualityReport:
        """
        Audit a DataFrame and generate a DataQualityReport.
        Rejects dataset if Quality Score < 95.0 or schema validation fails.
        """
        total_records = len(df)
        if total_records == 0:
            raise DataValidationError("Dataset is empty! Zero records found.")

        missing_cols = [col for col in expected_columns if col not in df.columns]
        schema_passed = len(missing_cols) == 0

        missing_values_count = int(df[expected_columns].isnull().sum().sum()) if schema_passed else total_records
        duplicate_rows_count = int(df.duplicated(subset=['timestamp', 'symbol']).sum()) if 'timestamp' in df and 'symbol' in df else 0

        total_cells = total_records * len(expected_columns)
        completeness_percent = max(0.0, ((total_cells - missing_values_count) / total_cells) * 100.0) if total_cells > 0 else 0.0

        dup_penalty = (duplicate_rows_count / total_records) * 50.0 if total_records > 0 else 50.0
        quality_score = max(0.0, completeness_percent - dup_penalty)
        if not schema_passed:
            quality_score = 0.0

        calendar_passed = self._check_calendar(df, self.calendar)
        oi_integrity_passed = self._check_oi_integrity(df) if "open_interest" in expected_columns and schema_passed else True

        if not calendar_passed or not oi_integrity_passed:
            quality_score = 0.0

        checksum = self.compute_sha256(df)
        status = (
            "ACCEPTED"
            if quality_score >= self.QUALITY_THRESHOLD
            and schema_passed
            and calendar_passed
            and oi_integrity_passed
            else "REJECTED"
        )

        return DataQualityReport(
            dataset_name=dataset_name,
            total_records=total_records,
            unique_symbols=int(df['symbol'].nunique()) if 'symbol' in df else 0,
            missing_values_count=missing_values_count,
            duplicate_rows_count=duplicate_rows_count,
            completeness_percent=round(completeness_percent, 2),
            schema_passed=schema_passed,
            calendar_passed=calendar_passed,
            oi_integrity_passed=oi_integrity_passed,
            checksum_sha256=checksum,
            quality_score=round(quality_score, 2),
            status=status
        )
