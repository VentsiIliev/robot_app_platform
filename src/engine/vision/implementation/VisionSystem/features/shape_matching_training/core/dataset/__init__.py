"""
Dataset Generation and Management Module

Provides tools for synthetic contour generation, data augmentation,
and training pair creation.
"""

from .shape_factory import ShapeFactory
from .synthetic_dataset import SyntheticDataset, SyntheticContour
from .data_augmentation import ContourAugmenter
from .pair_generator import PairGenerator

__all__ = [
    'ShapeFactory',
    'SyntheticDataset',
    'SyntheticContour',
    'ContourAugmenter',
    'PairGenerator'
]