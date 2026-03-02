"""
Glue Monitor System

A comprehensive system for monitoring glue dispensing cells, managing state,
and coordinating glue dispensing operations.

Public API - Import from submodules:
    Core Components:
        from glue_monitor_system.core.cell_manager import GlueCellsManagerSingleton
        from glue_monitor_system.core.meter import GlueMeter
        from glue_monitor_system.core.state_machine import StateManager, CellStateMonitor

    Services:
        from glue_monitor_system.services.legacy_fetcher import GlueDataFetcher
        from glue_monitor_system.services.fetcher import WeightDataFetcher
        from glue_monitor_system.services.factory import get_service_factory

    Configuration:
        from glue_monitor_system.config.loader import load_config
        from glue_monitor_system.config.validator import ConfigValidator

    Models:
        from glue_monitor_system.models.cells import CellConfig
        from glue_monitor_system.models.dto import GlueCellsResponseDTO
"""

# Note: No eager imports to avoid circular dependencies
# Users should import from submodules directly

__all__ = [
    # Core
    'GlueCellsManagerSingleton',
    'GlueMeter',
    'StateManager',
    'CellStateMonitor',
    'CellState',
    'ServiceState',

    # Services
    'GlueDataFetcher',
    'WeightDataFetcher',
    'get_service_factory',

    # Configuration
    'load_config',
    'ConfigValidator',
    'ConfigurationError',

    # Models
    'CellConfig',
    'GlueCellsResponseDTO',
    'CellUpdateRequestDTO',

    # Utils
    'handle_connection_error',
    'handle_timeout',
    'handle_HTTPError',
]
