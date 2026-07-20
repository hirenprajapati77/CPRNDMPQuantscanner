"""
NDMP OS v6.0 - BaseFeature Immutable Software Contract
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import pandas as pd


class BaseFeature(ABC):
    """
    Abstract Base Class defining the immutable software contract for all NDMP OS features.
    Every feature in ndmp-research/features must inherit from this class.
    """

    def __init__(self, feature_id: str, manifest_path: str | None = None):
        self.feature_id = feature_id
        self.manifest_path = manifest_path

    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """
        Compute feature values from normalized OHLCV + OI data dataframe.
        
        Args:
            df (pd.DataFrame): Dataframe with standard columns ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'open_interest', 'vwap']
            
        Returns:
            pd.Series: Computed feature values indexed aligned with input df.
        """
        pass

    @abstractmethod
    def validate(self, series: pd.Series) -> bool:
        """
        Run runtime quality and zero look-ahead bias validation checks on computed feature series.
        
        Args:
            series (pd.Series): Feature output series to validate.
            
        Returns:
            bool: True if valid and clean of NaNs/Infs/look-ahead leakage, False otherwise.
        """
        pass

    @abstractmethod
    def metadata(self) -> Dict[str, Any]:
        """
        Return metadata dictionary detailing feature description, tier, category, and parameters.
        """
        pass

    @abstractmethod
    def version(self) -> str:
        """
        Return semantic version string (e.g., '1.0.0').
        """
        pass

    @abstractmethod
    def dependencies(self) -> List[str]:
        """
        Return list of input data column dependencies required by this feature.
        """
        pass
