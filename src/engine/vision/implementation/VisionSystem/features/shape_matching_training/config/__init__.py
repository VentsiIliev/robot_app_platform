"""
Configuration Management Module

Provides configuration classes and utilities for the shape matching training system.
Supports hierarchical configuration, validation, and environment-specific settings.
"""

from .base_config import BaseConfig
from .model_configs import ModelConfigRegistry
from .training_configs import DefaultTrainingConfig, RobustTrainingConfig, FastTrainingConfig

__all__ = [
    'BaseConfig',
    'ModelConfigRegistry',
    'DefaultTrainingConfig', 
    'RobustTrainingConfig',
    'FastTrainingConfig'
]