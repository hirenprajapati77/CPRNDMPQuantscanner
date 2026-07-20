"""
NDMP OS v6.0 - Data Schemas & Dataset Manifest Contracts
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class DatasetManifest(BaseModel):
    """Dataset Metadata & Reproducibility Version Manifest."""
    dataset_id: str = Field(..., description="Unique dataset identifier, e.g., NSE_FO_5YR")
    version: str = Field(..., description="Semantic dataset version, e.g., 1.0.0")
    source: str = Field(default="NSE", description="Data source provider")
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    symbols_count: int = Field(..., ge=1, description="Number of unique F&O stock symbols")
    row_count: int = Field(..., ge=1, description="Total row count in dataset")
    checksum_sha256: str = Field(..., description="SHA-256 hash of dataset")
    timezone: str = Field(default="Asia/Kolkata")
    time_frame: str = Field(..., description="Candle timeframe, e.g., 1m, 15m, 1d")


class OHLCVRecord(BaseModel):
    """Validated OHLCV + OI Data Record Contract."""
    timestamp: datetime
    symbol: str
    open: float = Field(..., gt=0)
    high: float = Field(..., gt=0)
    low: float = Field(..., gt=0)
    close: float = Field(..., gt=0)
    volume: int = Field(..., ge=0)
    open_interest: int = Field(..., ge=0)
    vwap: float = Field(..., gt=0)
    delivery_volume: Optional[int] = Field(default=None, ge=0)
