"""
Service factory for creating glue monitor system components.
Provides dependency injection and centralized component creation.
"""
from pathlib import Path
from typing import Optional
from modules.shared.MessageBroker import MessageBroker
from communication_layer.api.v1.topics import GlueCellTopics
from modules.shared.tools.glue_monitor_system.config.loader import load_config
from modules.shared.tools.glue_monitor_system.config.validator import GlueMonitorConfig
from modules.shared.tools.glue_monitor_system.interfaces.protocols import (
    IWeightDataFetcher, IGlueCellsManager, IConfigurationManager, IDataPublisher
)
from modules.shared.tools.glue_monitor_system.services.fetcher import WeightDataFetcher
from modules.shared.tools.glue_monitor_system.core.cell_manager import GlueCellsManagerSingleton
from core.application.ApplicationStorageResolver import get_app_settings_path
from modules.utils import PathResolver


class ConfigurationManager(IConfigurationManager):
    """Configuration manager implementation."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or self._get_default_config_path()
        self._config: Optional[GlueMonitorConfig] = None
    
    def _get_default_config_path(self) -> Path:
        """Get the default configuration path."""
        try:
            return Path(get_app_settings_path("glue_dispensing_application", "glue_cell_config"))
        except ImportError:
            return Path(PathResolver.get_settings_file_path('glue_cell_config.json'))
    
    def load_config(self) -> GlueMonitorConfig:
        """Load and validate configuration."""
        self._config = load_config(self._config_path)
        return self._config
    
    def reload_config(self) -> GlueMonitorConfig:
        """Reload configuration from disk."""
        return self.load_config()
    
    def get_config(self) -> GlueMonitorConfig:
        """Get current configuration."""
        if self._config is None:
            return self.load_config()
        return self._config


class DataPublisher(IDataPublisher):
    """Publisher for weight data to message brokers."""
    
    def __init__(self):

        self.broker = MessageBroker()
        self.topics = GlueCellTopics
    
    def publish_weights(self, weights: dict[int, float]) -> None:
        """Publish weight data to relevant topics."""
        for cell_id, weight in weights.items():
            self.publish_cell_weight(cell_id, weight)
    
    def publish_cell_weight(self, cell_id: int, weight: float) -> None:
        """Publish single cell weight."""
        if cell_id == 1:
            self.broker.publish(self.topics.CELL_1_WEIGHT, weight)
        elif cell_id == 2:
            self.broker.publish(self.topics.CELL_2_WEIGHT, weight)
        elif cell_id == 3:
            self.broker.publish(self.topics.CELL_3_WEIGHT, weight)


class GlueMonitorServiceFactory:
    """Factory for creating glue monitor system services."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_manager = ConfigurationManager(config_path)
        self.data_publisher = DataPublisher()
        self._data_fetcher: Optional[IWeightDataFetcher] = None
        self._cells_manager: Optional[IGlueCellsManager] = None
    
    def create_configuration_manager(self) -> IConfigurationManager:
        """Create a configuration manager."""
        return self.config_manager
    
    def create_data_publisher(self) -> IDataPublisher:
        """Create a data publisher."""
        return self.data_publisher
    
    def create_weight_data_fetcher(self) -> IWeightDataFetcher:
        """Create a weight data fetcher with dependency injection."""
        if self._data_fetcher is None:
            self._data_fetcher = WeightDataFetcher(self.config_manager, self.data_publisher)
        return self._data_fetcher
    
    def create_cells_manager(self) -> IGlueCellsManager:
        """Create a cells manager with dependency injection."""
        if self._cells_manager is None:
            # Use the existing singleton instance
            self._cells_manager = GlueCellsManagerSingleton.get_instance()

        return self._cells_manager
    
    def get_config(self) -> GlueMonitorConfig:
        """Get current configuration."""
        return self.config_manager.get_config()


# Global factory instance for backward compatibility
_global_factory: Optional[GlueMonitorServiceFactory] = None


def get_service_factory() -> GlueMonitorServiceFactory:
    """Get the global service factory instance."""
    global _global_factory
    if _global_factory is None:
        _global_factory = GlueMonitorServiceFactory()
    return _global_factory


def create_weight_data_fetcher() -> IWeightDataFetcher:
    """Create a weight data fetcher using the factory."""
    return get_service_factory().create_weight_data_fetcher()


def create_cells_manager() -> IGlueCellsManager:
    """Create cells manager using the factory."""
    return get_service_factory().create_cells_manager()


def create_configuration_manager() -> IConfigurationManager:
    """Create a configuration manager using the factory."""
    return get_service_factory().create_configuration_manager()


def create_data_publisher() -> IDataPublisher:
    """Create a data publisher using the factory."""
    return get_service_factory().create_data_publisher()