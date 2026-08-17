"""
NDMP OS v6.0 - Environment Configuration Manager
"""

import os
from typing import Dict, Any
import yaml
from pydantic import BaseModel


class EngineConfig(BaseModel):
    environment: str = "dev"
    max_scan_workers: int = 4
    scan_cutoff_time_ist: str = "15:23:00"
    universe_size: int = 180
    data_dir: str = "data/parquet"
    log_level: str = "INFO"


class GovernanceConfig(BaseModel):
    min_oos_profit_factor: float = 1.80
    min_deflated_sharpe: float = 1.50
    max_pbo_percent: float = 10.0
    max_shap_stability_var: float = 2.50
    min_marginal_ev_gain: float = 0.35
    frictional_cost_percent: float = 0.15  # percent units, e.g. 0.15 == 0.15%

    @property
    def frictional_cost_decimal(self) -> float:
        """Per-trade friction as a decimal return (0.15% -> 0.0015)."""
        return self.frictional_cost_percent / 100.0


class FyersConfig(BaseModel):
    """Config for NDMP OS's own Fyers market-data connection — deliberately
    separate from CPR Pro's Fyers auth/token setup, per project decision to
    keep the two platforms' credentials independent."""
    client_id_env: str = "FYERS_CLIENT_ID"
    token_enc_key_env: str = "FYERS_TOKEN_ENC_KEY"
    token_encrypted_env: str = "FYERS_ACCESS_TOKEN_ENCRYPTED"
    oi_poll_interval_seconds: int = 30
    oi_data_dir: str = "data/oi_history"


class AngelOneConfig(BaseModel):
    """Config for NDMP OS's Angel One SmartAPI connection — the OI data source
    of record for NDMP OS going forward (CPR Pro continues to use Fyers)."""
    client_code_env: str = "ANGELONE_CLIENT_CODE"
    token_enc_key_env: str = "ANGELONE_TOKEN_ENC_KEY"
    access_token_encrypted_env: str = "ANGELONE_ACCESS_TOKEN_ENCRYPTED"
    api_key_env: str = "ANGELONE_API_KEY"
    oi_poll_interval_seconds: int = 30
    oi_data_dir: str = "data/oi_history_angelone"
    instrument_master_cache_path: str = "data/angelone_instrument_master.json"


class SystemConfig(BaseModel):
    engine: EngineConfig = EngineConfig()
    governance: GovernanceConfig = GovernanceConfig()
    fyers: FyersConfig = FyersConfig()
    angelone: AngelOneConfig = AngelOneConfig()

    @classmethod
    def load_from_yaml(cls, yaml_path: str) -> "SystemConfig":
        """Load configuration from YAML file."""
        if not os.path.exists(yaml_path):
            return cls()
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)


# Shared default configuration — single source of truth for gate thresholds and friction.
DEFAULT_CONFIG = SystemConfig()
