"""
Service interfaces and abstractions for the glue monitor system.
Enables dependency injection and testability.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from modules.shared.tools.glue_monitor_system.config.validator import GlueMonitorConfig


class IWeightDataFetcher(ABC):
    """Interface for weight data fetching services."""
    
    @abstractmethod
    def start(self) -> None:
        """Start the data fetching process."""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop the data fetching process."""
        pass
    
    @abstractmethod
    def get_weights(self) -> Dict[int, float]:
        """Get current weights for all cells."""
        pass
    
    @abstractmethod
    def get_weight(self, cell_id: int) -> Optional[float]:
        """Get weight for a specific cell."""
        pass
    
    @abstractmethod
    def reload_config(self) -> None:
        """Reload configuration and restart with new settings."""
        pass


class IGlueCell(ABC):
    """Interface for glue cell objects."""
    
    @property
    @abstractmethod
    def id(self) -> int:
        """Cell unique identifier."""
        pass
    
    @property
    @abstractmethod
    def glue_type(self) -> str:
        """Current glue type in this cell (e.g., "Type A", "Custom Glue X")."""
        pass
    
    @property
    @abstractmethod
    def capacity(self) -> float:
        """Cell capacity in grams."""
        pass
    
    @abstractmethod
    def get_weight(self) -> Optional[float]:
        """Get current weight in grams."""
        pass
    
    @abstractmethod
    def get_percentage(self) -> Optional[float]:
        """Get current fill percentage."""
        pass
    
    @abstractmethod
    def set_glue_type(self, glue_type: str) -> None:
        """Set the glue type for this cell."""
        pass


class IGlueCellsManager(ABC):
    """Interface for managing multiple glue cells."""
    
    @abstractmethod
    def get_cell_by_id(self, cell_id: int) -> Optional[IGlueCell]:
        """Get a cell by its ID."""
        pass
    
    @abstractmethod
    def get_all_cells(self) -> List[IGlueCell]:
        """Get all managed cells."""
        pass
    
    @abstractmethod
    def update_glue_type_by_id(self, cell_id: int, glue_type: str) -> bool:
        """Update glue type for a specific cell and persist changes."""
        pass
    
    @abstractmethod
    def poll_glue_data_by_id(self, cell_id: int) -> tuple[Optional[float], Optional[float]]:
        """Get weight and percentage for a specific cell."""
        pass


class IGlueMeter(ABC):
    """Interface for individual glue meters."""
    
    @property
    @abstractmethod
    def id(self) -> int:
        """Meter unique identifier."""
        pass
    
    @property
    @abstractmethod
    def state(self) -> str:
        """Current connection/operational state."""
        pass
    
    @abstractmethod
    def fetch_data(self) -> Optional[float]:
        """Fetch current weight data."""
        pass
    
    @abstractmethod
    def test_connection(self) -> None:
        """Test meter connection."""
        pass


class IConfigurationManager(ABC):
    """Interface for configuration management."""
    
    @abstractmethod
    def load_config(self) -> GlueMonitorConfig:
        """Load and validate configuration."""
        pass
    
    @abstractmethod
    def reload_config(self) -> GlueMonitorConfig:
        """Reload configuration from disk."""
        pass
    
    @abstractmethod
    def get_config(self) -> GlueMonitorConfig:
        """Get current configuration."""
        pass


class IDataPublisher(ABC):
    """Interface for publishing weight data to message brokers."""
    
    @abstractmethod
    def publish_weights(self, weights: Dict[int, float]) -> None:
        """Publish weight data to relevant topics."""
        pass
    
    @abstractmethod
    def publish_cell_weight(self, cell_id: int, weight: float) -> None:
        """Publish single cell weight."""
        pass