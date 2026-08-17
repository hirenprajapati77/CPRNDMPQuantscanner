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


class DataSourceIntegrityError(NDMPError):
    """Raised when an input column is present but structurally incapable of carrying
    real signal (e.g. a constant/frozen value across the full series), indicating
    the upstream data source does not actually provide this data."""
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


class FyersAuthError(BrokerError):
    """Raised when Fyers access token env vars are missing, malformed, or fail to decrypt."""
    pass


class FyersTokenRefreshError(FyersAuthError):
    """Raised when the daily refresh_token -> access_token exchange with Fyers fails
    (expired/invalid refresh_token, wrong PIN, network error, or malformed response)."""
    pass


class FyersAPIError(BrokerError):
    """Raised when a Fyers API call fails or returns an unexpected/non-ok response shape."""
    pass


class AngelOneAuthError(BrokerError):
    """Raised when Angel One session/access token env vars are missing, malformed,
    fail to decrypt, or the daily session has expired."""
    pass


class AngelOneAPIError(BrokerError):
    """Raised when an Angel One SmartAPI call fails or returns an unexpected/non-ok
    response shape."""
    pass


class AngelOneInstrumentLookupError(BrokerError):
    """Raised when a trading symbol cannot be resolved to an Angel One symboltoken
    via the instrument master (unknown symbol, stale/unfetchable master file)."""
    pass
