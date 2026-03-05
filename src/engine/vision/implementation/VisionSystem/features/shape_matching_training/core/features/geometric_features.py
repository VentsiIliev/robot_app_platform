"""
Geometric Feature Extractor

Extracts geometric properties from contours including area ratios,
perimeter features, and shape descriptors.
"""

import cv2
import numpy as np
from typing import List, Dict, Any
from .base_extractor import BaseFeatureExtractor


class GeometricFeatureExtractor(BaseFeatureExtractor):
    """
    Extracts geometric features from contours including:
    - Aspect ratio
    - Extent  
    - Solidity
    - Convexity ratio
    - Equivalent diameter
    - Perimeter
    - Compactness
    - Eccentricity
    - Major/minor axis lengths
    """
    
    def __init__(self, config: Dict[str, Any] = None, **kwargs):
        """
        Initialize geometric feature extractor
        
        Args:
            config: Configuration dictionary (currently unused)
            **kwargs: Alternative way to pass configuration parameters directly
        """
        # Merge config dict and kwargs
        if config is None:
            config = {}
        config = {**config, **kwargs}

        super().__init__(config)
    
    def extract_features(self, contour: np.ndarray) -> List[float]:
        """
        Extract geometric features from contour
        
        Args:
            contour: OpenCV contour array
            
        Returns:
            List of 9 geometric features
        """
        features = []
        
        try:
            # Basic geometric properties
            features.append(self._aspect_ratio(contour))
            features.append(self._extent(contour))
            features.append(self._solidity(contour))
            features.append(self._convexity_ratio(contour))
            features.append(self._equivalent_diameter(contour))
            features.append(self._perimeter(contour))
            features.append(self._compactness(contour))
            features.append(self._eccentricity(contour))
            features.append(self._major_minor_axis_ratio(contour))
            
        except Exception as e:
            # Return zeros for invalid contours
            print(f"Warning: Error extracting geometric features: {e}")
            features = [0.0] * 9
        
        return features
    
    def get_feature_names(self) -> List[str]:
        """Get names of geometric features"""
        return [
            'aspect_ratio',
            'extent', 
            'solidity',
            'convexity_ratio',
            'equivalent_diameter',
            'perimeter',
            'compactness',
            'eccentricity',
            'major_minor_axis_ratio'
        ]
    
    def get_feature_count(self) -> int:
        """Get number of geometric features"""
        return 9
    
    def _aspect_ratio(self, contour: np.ndarray) -> float:
        """Aspect ratio of bounding rectangle"""
        try:
            x, y, w, h = cv2.boundingRect(contour)
            if h == 0:
                return 0.0
            return float(w) / float(h)
        except:
            return 0.0
    
    def _extent(self, contour: np.ndarray) -> float:
        """Extent = contour area / bounding rectangle area"""
        try:
            area = cv2.contourArea(contour)
            x, y, w, h = cv2.boundingRect(contour)
            rect_area = w * h
            if rect_area == 0:
                return 0.0
            return float(area) / float(rect_area)
        except:
            return 0.0
    
    def _solidity(self, contour: np.ndarray) -> float:
        """Solidity = contour area / convex hull area"""
        try:
            hull = cv2.convexHull(contour)
            hull_area = cv2.contourArea(hull)
            if hull_area == 0:
                return 0.0
            return cv2.contourArea(contour) / hull_area
        except:
            return 0.0
    
    def _convexity_ratio(self, contour: np.ndarray) -> float:
        """Same as solidity - convexity ratio"""
        return self._solidity(contour)
    
    def _equivalent_diameter(self, contour: np.ndarray) -> float:
        """Equivalent diameter = sqrt(4*Area/pi)"""
        try:
            area = cv2.contourArea(contour)
            if area <= 0:
                return 0.0
            return np.sqrt(4 * area / np.pi)
        except:
            return 0.0
    
    def _perimeter(self, contour: np.ndarray) -> float:
        """Perimeter of the contour"""
        try:
            return cv2.arcLength(contour, True)
        except:
            return 0.0
    
    def _compactness(self, contour: np.ndarray) -> float:
        """Compactness = (perimeter^2) / (4*pi*area)"""
        try:
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            
            if area <= 0:
                return 0.0
            
            return (perimeter ** 2) / (4 * np.pi * area)
        except:
            return 0.0
    
    def _eccentricity(self, contour: np.ndarray) -> float:
        """Eccentricity from fitted ellipse"""
        try:
            if len(contour) < 5:  # Need at least 5 points to fit ellipse
                return 0.0
            
            ellipse = cv2.fitEllipse(contour)
            (center, axes, orientation) = ellipse
            major_axis = max(axes)
            minor_axis = min(axes)
            
            if major_axis == 0:
                return 0.0
            
            # Eccentricity calculation
            eccentricity = np.sqrt(1 - (minor_axis / major_axis) ** 2)
            return eccentricity
        except:
            return 0.0
    
    def _major_minor_axis_ratio(self, contour: np.ndarray) -> float:
        """Ratio of major axis to minor axis from fitted ellipse"""
        try:
            if len(contour) < 5:  # Need at least 5 points to fit ellipse
                return 1.0
            
            ellipse = cv2.fitEllipse(contour)
            (center, axes, orientation) = ellipse
            major_axis = max(axes)
            minor_axis = min(axes)
            
            if minor_axis == 0:
                return 0.0
            
            return major_axis / minor_axis
        except:
            return 1.0


class AreaFeatureExtractor(BaseFeatureExtractor):
    """
    Specialized extractor for area-based features including
    scale-sensitive area differences and scale band categorization
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize area feature extractor
        
        Args:
            config: Configuration with optional 'n_bands' parameter
        """
        super().__init__(config)
        self.n_bands = self.config.get('n_bands', 5)
    
    def extract_features(self, contour: np.ndarray) -> List[float]:
        """
        Extract area-based features from contour
        
        Args:
            contour: OpenCV contour array
            
        Returns:
            List of area features
        """
        features = []
        
        try:
            area = cv2.contourArea(contour)
            features.append(area)  # Raw area (scale-sensitive)
            features.append(self._equivalent_diameter(contour))
            
        except Exception as e:
            print(f"Warning: Error extracting area features: {e}")
            features = [0.0] * 2
        
        return features
    
    def get_feature_names(self) -> List[str]:
        """Get names of area features"""
        return ['area', 'equivalent_diameter']
    
    def get_feature_count(self) -> int:
        """Get number of area features"""
        return 2
    
    def _equivalent_diameter(self, contour: np.ndarray) -> float:
        """Equivalent diameter = sqrt(4*Area/pi)"""
        try:
            area = cv2.contourArea(contour)
            if area <= 0:
                return 0.0
            return np.sqrt(4 * area / np.pi)
        except:
            return 0.0
    
    def scale_band_categorical(self, area1: float, area2: float) -> float:
        """
        Classify areas into discrete bands and return categorical difference
        
        Args:
            area1: Area of first contour
            area2: Area of second contour
            
        Returns:
            Categorical difference between scale bands (0-1)
        """
        # Define scale bands
        max_area = max(area1, area2, 10000)  # Ensure reasonable max
        band_size = max_area / self.n_bands
        
        band1 = min(int(area1 / band_size), self.n_bands - 1)
        band2 = min(int(area2 / band_size), self.n_bands - 1)
        
        return abs(band1 - band2) / (self.n_bands - 1)  # Normalize to 0-1


# Register extractors with factory
from .base_extractor import FeatureExtractorFactory

FeatureExtractorFactory.register_extractor('geometric', GeometricFeatureExtractor)
FeatureExtractorFactory.register_extractor('area', AreaFeatureExtractor)