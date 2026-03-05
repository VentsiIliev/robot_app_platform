"""
Model Implementation Module

Provides machine learning model implementations and factory for creating
and managing different types of contour similarity classifiers.
"""

from .base_model import BaseModel
from .sgd_model import SGDModel
from .model_factory import ModelFactory

__all__ = [
    'BaseModel',
    'SGDModel', 
    'ModelFactory'
]