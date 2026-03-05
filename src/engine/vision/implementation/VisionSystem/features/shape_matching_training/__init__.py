"""
Shape Matching Training Module

A comprehensive machine learning system for contour similarity detection and matching.
This module provides tools for synthetic data generation, feature extraction, model training,
and real-time shape matching applications.
"""

from .core.training.pipeline import TrainingPipeline
from .core.models.model_factory import ModelFactory
from .config.training_configs import DefaultTrainingConfig
from .utils.io_utils import load_model, save_model

__version__ = "2.0.0"
__author__ = "Shape Matching Training System"

# Main public API
__all__ = [
    'TrainingPipeline',
    'ModelFactory', 
    'DefaultTrainingConfig',
    'load_model',
    'save_model'
]