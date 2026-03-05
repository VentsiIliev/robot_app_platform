"""
Abstract Base Feature Extractor

Provides the abstract base class and factory for feature extraction,
establishing a consistent interface for all feature extraction methods.
"""

import numpy as np
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union, Optional, Type
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp


class BaseFeatureExtractor(ABC):
    """
    Abstract base class for feature extractors.
    
    All feature extractors must implement the extract_features method
    and provide metadata about the features they generate.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize feature extractor with configuration
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self._validate_config()
    
    @abstractmethod
    def extract_features(self, contour: np.ndarray) -> List[float]:
        """
        Extract features from a single contour
        
        Args:
            contour: OpenCV contour array
            
        Returns:
            List of extracted feature values
        """
        pass
    
    @abstractmethod
    def get_feature_names(self) -> List[str]:
        """
        Get names of the features extracted by this extractor
        
        Returns:
            List of feature names in the same order as extract_features output
        """
        pass
    
    @abstractmethod
    def get_feature_count(self) -> int:
        """
        Get the number of features extracted by this extractor
        
        Returns:
            Number of features
        """
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about this feature extractor
        
        Returns:
            Dictionary with extractor metadata
        """
        return {
            'extractor_type': self.__class__.__name__,
            'feature_count': self.get_feature_count(),
            'feature_names': self.get_feature_names(),
            'config': self.config,
            'version': self.get_version()
        }
    
    def get_version(self) -> str:
        """
        Get version string for this extractor
        
        Returns:
            Version string
        """
        return "1.0.0"
    
    def _validate_config(self) -> None:
        """
        Validate the configuration dictionary.
        Override in subclasses for specific validation.
        """
        pass
    
    def extract_features_parallel(self, contours: List[np.ndarray]) -> List[List[float]]:
        """
        Extract features from multiple contours in parallel
        
        Args:
            contours: List of contours
            
        Returns:
            List of feature vectors
        """
        if len(contours) == 1:
            return [self.extract_features(contours[0])]
        
        # Use parallel processing for multiple contours
        n_cores = min(mp.cpu_count(), 8, len(contours))
        
        with ProcessPoolExecutor(max_workers=n_cores) as executor:
            features = list(executor.map(self.extract_features, contours))
        
        return features


class CompositeFeatureExtractor(BaseFeatureExtractor):
    """
    Composite feature extractor that combines multiple extractors
    """
    
    def __init__(self, extractors: List[BaseFeatureExtractor]):
        """
        Initialize with list of extractors
        
        Args:
            extractors: List of feature extractors to combine
        """
        self.extractors = extractors
        super().__init__()
    
    def extract_features(self, contour: np.ndarray) -> List[float]:
        """Extract features using all extractors"""
        features = []
        for extractor in self.extractors:
            features.extend(extractor.extract_features(contour))
        return features
    
    def get_feature_names(self) -> List[str]:
        """Get all feature names from all extractors"""
        names = []
        for extractor in self.extractors:
            extractor_names = extractor.get_feature_names()
            # Prefix with extractor type to avoid name collisions
            extractor_type = extractor.__class__.__name__.replace('FeatureExtractor', '')
            prefixed_names = [f"{extractor_type}_{name}" for name in extractor_names]
            names.extend(prefixed_names)
        return names
    
    def get_feature_count(self) -> int:
        """Get total feature count from all extractors"""
        return sum(extractor.get_feature_count() for extractor in self.extractors)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata including all sub-extractors"""
        metadata = super().get_metadata()
        metadata['sub_extractors'] = [extractor.get_metadata() for extractor in self.extractors]
        return metadata


class FeatureExtractorFactory:
    """
    Factory for creating and managing feature extractors
    """
    
    _extractors: Dict[str, Type[BaseFeatureExtractor]] = {}
    
    @classmethod
    def register_extractor(cls, name: str, extractor_class: Type[BaseFeatureExtractor]) -> None:
        """
        Register a feature extractor class
        
        Args:
            name: Name to register the extractor under
            extractor_class: Feature extractor class
        """
        cls._extractors[name] = extractor_class
    
    @classmethod
    def create_extractor(cls, name: str, config: Optional[Dict[str, Any]] = None) -> BaseFeatureExtractor:
        """
        Create a feature extractor by name
        
        Args:
            name: Name of the extractor to create
            config: Optional configuration dictionary
            
        Returns:
            Initialized feature extractor
            
        Raises:
            ValueError: If extractor name is not registered
        """
        if name not in cls._extractors:
            available = list(cls._extractors.keys())
            raise ValueError(f"Unknown extractor '{name}'. Available: {available}")
        
        extractor_class = cls._extractors[name]
        return extractor_class(config)
    
    @classmethod
    def create_composite_extractor(cls, 
                                  extractor_configs: List[Dict[str, Any]]) -> CompositeFeatureExtractor:
        """
        Create a composite extractor from a list of configurations
        
        Args:
            extractor_configs: List of extractor configurations, each containing 'name' and optional 'config'
            
        Returns:
            Composite feature extractor
        """
        extractors = []
        for config in extractor_configs:
            name = config['name']
            extractor_config = config.get('config', {})
            extractor = cls.create_extractor(name, extractor_config)
            extractors.append(extractor)
        
        return CompositeFeatureExtractor(extractors)
    
    @classmethod
    def list_available_extractors(cls) -> List[str]:
        """
        List all registered extractor names
        
        Returns:
            List of registered extractor names
        """
        return list(cls._extractors.keys())
    
    @classmethod
    def get_extractor_info(cls, name: str) -> Dict[str, Any]:
        """
        Get information about a registered extractor
        
        Args:
            name: Name of the extractor
            
        Returns:
            Dictionary with extractor information
        """
        if name not in cls._extractors:
            raise ValueError(f"Unknown extractor '{name}'")
        
        extractor_class = cls._extractors[name]
        # Create temporary instance to get metadata
        temp_extractor = extractor_class({})
        
        return {
            'name': name,
            'class': extractor_class.__name__,
            'feature_count': temp_extractor.get_feature_count(),
            'feature_names': temp_extractor.get_feature_names(),
            'version': temp_extractor.get_version(),
            'docstring': extractor_class.__doc__
        }


# Utility functions for feature extraction pipeline
def compute_features_for_pair(contour_pair: tuple, 
                             extractor: BaseFeatureExtractor) -> List[float]:
    """
    Compute features for a pair of contours (difference features)
    
    Args:
        contour_pair: Tuple of (contour1, contour2)
        extractor: Feature extractor to use
        
    Returns:
        List of difference features
    """
    contour1, contour2 = contour_pair
    
    # Extract features for each contour
    features1 = np.array(extractor.extract_features(contour1))
    features2 = np.array(extractor.extract_features(contour2))
    
    # Compute difference features
    diff_features = np.abs(features1 - features2)
    
    return diff_features.tolist()


def compute_features_parallel(contour_pairs: List[tuple],
                            extractor: BaseFeatureExtractor,
                            max_workers: Optional[int] = None) -> List[List[float]]:
    """
    Compute features for multiple contour pairs in parallel
    
    Args:
        contour_pairs: List of (contour1, contour2) tuples
        extractor: Feature extractor to use
        max_workers: Maximum number of worker processes
        
    Returns:
        List of feature vectors for each pair
    """
    if max_workers is None:
        max_workers = min(mp.cpu_count(), 8)
    
    if len(contour_pairs) == 1:
        return [compute_features_for_pair(contour_pairs[0], extractor)]
    
    # Create worker function that captures the extractor
    def worker(pair):
        return compute_features_for_pair(pair, extractor)
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        features = list(executor.map(worker, contour_pairs))
    
    return features


def get_feature_extraction_metadata(extractor: BaseFeatureExtractor) -> Dict[str, Any]:
    """
    Get comprehensive metadata about feature extraction process
    
    Args:
        extractor: Feature extractor instance
        
    Returns:
        Dictionary with feature extraction metadata
    """
    metadata = extractor.get_metadata()
    
    # Add additional system information
    metadata.update({
        'feature_extraction_version': '2.0.0',
        'total_features': extractor.get_feature_count(),
        'parallel_processing_available': True,
        'max_workers': min(mp.cpu_count(), 8)
    })
    
    return metadata