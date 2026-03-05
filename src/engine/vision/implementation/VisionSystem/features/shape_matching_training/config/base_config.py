"""
Base Configuration Classes

Provides abstract base classes and utilities for configuration management
with validation, inheritance, and serialization capabilities.
"""

import json
from abc import ABC, abstractmethod

# Optional YAML support
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Type, TypeVar
from pathlib import Path

T = TypeVar('T', bound='BaseConfig')


class ConfigValidationError(Exception):
    """Raised when configuration validation fails"""
    pass


@dataclass
class BaseConfig(ABC):
    """
    Abstract base class for all configuration objects.
    
    Provides common functionality for validation, serialization,
    and configuration inheritance.
    """
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        self.validate()
    
    @abstractmethod
    def validate(self) -> None:
        """
        Validate configuration parameters.
        
        Raises:
            ConfigValidationError: If validation fails
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return asdict(self)
    
    def to_json(self, filepath: Optional[Path] = None) -> str:
        """
        Convert configuration to JSON string or save to file.
        
        Args:
            filepath: Optional path to save JSON file
            
        Returns:
            JSON string representation
        """
        config_dict = self.to_dict()
        json_str = json.dumps(config_dict, indent=2, default=str)
        
        if filepath:
            filepath.write_text(json_str)
        
        return json_str
    
    def to_yaml(self, filepath: Optional[Path] = None) -> str:
        """
        Convert configuration to YAML string or save to file.
        
        Args:
            filepath: Optional path to save YAML file
            
        Returns:
            YAML string representation
            
        Raises:
            ImportError: If PyYAML is not installed
        """
        if not YAML_AVAILABLE:
            raise ImportError(
                "PyYAML is not installed. Install it with: pip install PyYAML\n"
                "Alternatively, use to_json() or save_to_file() for JSON format."
            )
        
        config_dict = self.to_dict()
        yaml_str = yaml.dump(config_dict, default_flow_style=False, indent=2)
        
        if filepath:
            filepath.write_text(yaml_str)
        
        return yaml_str
    
    @classmethod
    def from_dict(cls: Type[T], config_dict: Dict[str, Any]) -> T:
        """
        Create configuration from dictionary.
        
        Args:
            config_dict: Configuration parameters as dictionary
            
        Returns:
            Configuration instance
        """
        return cls(**config_dict)
    
    @classmethod
    def from_json(cls: Type[T], json_str_or_path: str) -> T:
        """
        Create configuration from JSON string or file.
        
        Args:
            json_str_or_path: JSON string or path to JSON file
            
        Returns:
            Configuration instance
        """
        try:
            # Try to parse as JSON string first
            config_dict = json.loads(json_str_or_path)
        except json.JSONDecodeError:
            # If parsing fails, treat as file path
            filepath = Path(json_str_or_path)
            if not filepath.exists():
                raise FileNotFoundError(f"Configuration file not found: {filepath}")
            config_dict = json.loads(filepath.read_text())
        
        return cls.from_dict(config_dict)
    
    @classmethod
    def from_yaml(cls: Type[T], yaml_str_or_path: str) -> T:
        """
        Create configuration from YAML string or file.
        
        Args:
            yaml_str_or_path: YAML string or path to YAML file
            
        Returns:
            Configuration instance
            
        Raises:
            ImportError: If PyYAML is not installed
        """
        if not YAML_AVAILABLE:
            raise ImportError(
                "PyYAML is not installed. Install it with: pip install PyYAML\n"
                "Alternatively, use from_json() or load_from_file() for JSON format."
            )
        
        try:
            # Try to parse as YAML string first
            config_dict = yaml.safe_load(yaml_str_or_path)
        except yaml.YAMLError:
            # If parsing fails, treat as file path
            filepath = Path(yaml_str_or_path)
            if not filepath.exists():
                raise FileNotFoundError(f"Configuration file not found: {filepath}")
            config_dict = yaml.safe_load(filepath.read_text())
        
        return cls.from_dict(config_dict)
    
    def merge(self: T, other: T) -> T:
        """
        Merge this configuration with another configuration.
        Other configuration takes precedence for conflicting values.
        
        Args:
            other: Configuration to merge with
            
        Returns:
            New merged configuration instance
        """
        self_dict = self.to_dict()
        other_dict = other.to_dict()
        
        # Recursively merge dictionaries
        merged_dict = self._deep_merge(self_dict, other_dict)
        
        return self.__class__.from_dict(merged_dict)
    
    @staticmethod
    def _deep_merge(dict1: Dict, dict2: Dict) -> Dict:
        """Recursively merge two dictionaries"""
        result = dict1.copy()
        
        for key, value in dict2.items():
            if (key in result and 
                isinstance(result[key], dict) and 
                isinstance(value, dict)):
                result[key] = BaseConfig._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def __str__(self) -> str:
        """String representation of configuration"""
        return f"{self.__class__.__name__}({self.to_dict()})"
    
    def __repr__(self) -> str:
        """Detailed string representation of configuration"""
        return self.__str__()


def validate_positive_number(value: float, name: str) -> None:
    """
    Validate that a value is a positive number.
    
    Args:
        value: Value to validate
        name: Parameter name for error messages
        
    Raises:
        ConfigValidationError: If validation fails
    """
    if not isinstance(value, (int, float)) or value <= 0:
        raise ConfigValidationError(f"{name} must be a positive number, got {value}")


def validate_probability(value: float, name: str) -> None:
    """
    Validate that a value is a valid probability (0-1).
    
    Args:
        value: Value to validate
        name: Parameter name for error messages
        
    Raises:
        ConfigValidationError: If validation fails
    """
    if not isinstance(value, (int, float)) or not (0 <= value <= 1):
        raise ConfigValidationError(f"{name} must be between 0 and 1, got {value}")


def validate_positive_integer(value: int, name: str) -> None:
    """
    Validate that a value is a positive integer.
    
    Args:
        value: Value to validate
        name: Parameter name for error messages
        
    Raises:
        ConfigValidationError: If validation fails
    """
    if not isinstance(value, int) or value <= 0:
        raise ConfigValidationError(f"{name} must be a positive integer, got {value}")


def validate_choice(value: Any, choices: list, name: str) -> None:
    """
    Validate that a value is one of the allowed choices.
    
    Args:
        value: Value to validate
        choices: List of allowed choices
        name: Parameter name for error messages
        
    Raises:
        ConfigValidationError: If validation fails
    """
    if value not in choices:
        raise ConfigValidationError(f"{name} must be one of {choices}, got {value}")