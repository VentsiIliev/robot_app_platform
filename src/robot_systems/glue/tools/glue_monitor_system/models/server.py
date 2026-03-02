"""
Shared server and system configuration models for glue monitor system.

These models can be safely imported by both backend and UI layers.
All models are immutable (frozen=True) to prevent accidental mutations.
"""
from dataclasses import dataclass
from typing import List
from .cells import CellConfig


@dataclass(frozen=True)
class ServerConfig:
    """Server configuration - all fields required."""
    host: str
    port: int
    protocol: str
    
    @property
    def base_url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"


@dataclass(frozen=True)
class EndpointsConfig:
    """API endpoints configuration - all fields required."""
    weights: str
    tare: str
    get_config: str
    update_config: str


@dataclass(frozen=True)
class GlobalSettings:
    """Global system settings - all fields required."""
    fetch_timeout_seconds: int
    data_fetch_interval_ms: int
    ui_update_interval_ms: int


@dataclass(frozen=True)
class GlueMonitorConfig:
    """Complete glue monitor system configuration."""
    environment: str
    server: ServerConfig
    endpoints: EndpointsConfig
    global_settings: GlobalSettings
    cells: List[CellConfig]
    
    @property
    def is_test_mode(self) -> bool:
        return self.environment.lower() == "test"
    
    @property
    def is_production_mode(self) -> bool:
        return self.environment.lower() == "production"