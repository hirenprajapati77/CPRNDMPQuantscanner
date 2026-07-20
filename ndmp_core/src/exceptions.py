"""
NDMP OS v6.0 - Exception Hierarchy Taxonomy
"""


class NDMPError(Exception):
    """Base exception for all NDMP OS errors."""
    pass


class DataValidationError(NDMPError):
    """Raised when incoming dataset fails schema validation or data quality checks."""
    pass


class MissingDependencyError(NDMPError):
    """Raised when a feature calculation is missing required input data columns."""
    pass


class FeatureCalculationError(NDMPError):
    """Raised when a feature plugin fails during computation."""
    pass


class GovernanceError(NDMPError):
    """Raised when a candidate model or feature fails statistical promotion gates."""
    pass


class ReplayError(NDMPError):
    """Raised when an error occurs during market replay historical simulation."""
    pass


class BrokerError(NDMPError):
    """Raised when an error occurs in broker API order execution adapters."""
    pass
