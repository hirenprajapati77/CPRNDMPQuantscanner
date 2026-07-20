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
    frictional_cost_percent: float = 0.15


class SystemConfig(BaseModel):
    engine: EngineConfig = EngineConfig()
    governance: GovernanceConfig = GovernanceConfig()

    @classmethod
    def load_from_yaml(cls, yaml_path: str) -> "SystemConfig":
        """Load configuration from YAML file."""
        if not os.path.exists(yaml_path):
            return cls()
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
