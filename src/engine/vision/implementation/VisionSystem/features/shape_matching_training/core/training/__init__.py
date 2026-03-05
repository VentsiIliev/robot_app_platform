"""
Training Pipeline Module

Provides training orchestration, model evaluation, and end-to-end
pipeline management for shape matching model development.
"""

from .trainer import ModelTrainer
from .evaluator import ModelEvaluator
from .pipeline import TrainingPipeline

__all__ = [
    'ModelTrainer',
    'ModelEvaluator',
    'TrainingPipeline'
]