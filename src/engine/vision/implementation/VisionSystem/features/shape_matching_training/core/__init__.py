"""
Core Business Logic Module

Contains the main business logic for shape matching training including:
- Dataset generation and management
- Feature extraction
- Model implementations
- Training orchestration
"""

from .dataset import ShapeFactory, SyntheticDataset
from .features import FeatureExtractorFactory
from .models import ModelFactory
from .training import TrainingPipeline

__all__ = [
    'ShapeFactory',
    'SyntheticDataset', 
    'FeatureExtractorFactory',
    'ModelFactory',
    'TrainingPipeline'
]