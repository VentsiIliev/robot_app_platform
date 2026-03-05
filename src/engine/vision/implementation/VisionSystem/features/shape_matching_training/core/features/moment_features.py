"""
Moment-Based Feature Extractor

Extracts moment invariants and other moment-based features from contours,
providing scale, rotation, and translation invariant shape descriptors.
"""

import cv2
import numpy as np
from typing import List, Dict, Any
from .base_extractor import BaseFeatureExtractor


class MomentFeatureExtractor(BaseFeatureExtractor):
    """
    Extracts moment-based features including:
    - Hu moments (7 invariant moments)
    - Central moments
    - Normalized central moments
    """
    
    def __init__(self, config: Dict[str, Any] = None, **kwargs):
        """
        Initialize moment feature extractor
        
        Args:
            config: Configuration dictionary with optional parameters:
                   - use_log_hu: Whether to use log-transformed Hu moments (default: True)
                   - include_central_moments: Whether to include central moments (default: False)
            **kwargs: Alternative way to pass configuration parameters directly
        """
        # Merge config dict and kwargs
        if config is None:
            config = {}
        config = {**config, **kwargs}

        super().__init__(config)
        self.use_log_hu = self.config.get('use_log_hu', True)
        self.include_central_moments = self.config.get('include_central_moments', False)
    
    def extract_features(self, contour: np.ndarray) -> List[float]:
        """
        Extract moment-based features from contour
        
        Args:
            contour: OpenCV contour array
            
        Returns:
            List of moment features (7 Hu moments + optional central moments)
        """
        features = []
        
        try:
            # Calculate moments
            moments = cv2.moments(contour)
            
            # Extract Hu moments
            hu_moments = cv2.HuMoments(moments).flatten()
            
            if self.use_log_hu:
                # Apply log transformation to Hu moments
                # Handle the sign for negative values
                hu_features = []
                for hu in hu_moments:
                    if hu == 0:
                        hu_features.append(0.0)
                    else:
                        # Use sign-preserving log transformation
                        hu_features.append(np.copysign(np.log10(np.abs(hu) + 1e-10), hu))
            else:
                hu_features = hu_moments.tolist()
            
            features.extend(hu_features)
            
            # Optionally include central moments
            if self.include_central_moments:
                central_moments = self._extract_central_moments(moments)
                features.extend(central_moments)
                
        except Exception as e:
            # Return zeros for invalid contours
            print(f"Warning: Error extracting moment features: {e}")
            base_features = 7  # Hu moments
            if self.include_central_moments:
                base_features += 6  # Additional central moments
            features = [0.0] * base_features
        
        return features
    
    def get_feature_names(self) -> List[str]:
        """Get names of moment features"""
        names = [
            'hu_moment_1', 'hu_moment_2', 'hu_moment_3', 'hu_moment_4',
            'hu_moment_5', 'hu_moment_6', 'hu_moment_7'
        ]
        
        if self.include_central_moments:
            names.extend([
                'central_moment_20', 'central_moment_02', 'central_moment_11',
                'central_moment_30', 'central_moment_03', 'central_moment_21'
            ])
        
        return names
    
    def get_feature_count(self) -> int:
        """Get number of moment features"""
        count = 7  # Hu moments
        if self.include_central_moments:
            count += 6  # Additional central moments
        return count
    
    def _extract_central_moments(self, moments: Dict) -> List[float]:
        """
        Extract normalized central moments
        
        Args:
            moments: OpenCV moments dictionary
            
        Returns:
            List of central moment features
        """
        try:
            # Area for normalization
            m00 = moments['m00']
            if m00 == 0:
                return [0.0] * 6
            
            # Central moments (normalized)
            central_moments = [
                moments['mu20'] / (m00 ** 2),  # μ20 / m00^2
                moments['mu02'] / (m00 ** 2),  # μ02 / m00^2  
                moments['mu11'] / (m00 ** 2),  # μ11 / m00^2
                moments['mu30'] / (m00 ** 2.5),  # μ30 / m00^2.5
                moments['mu03'] / (m00 ** 2.5),  # μ03 / m00^2.5
                moments['mu21'] / (m00 ** 2.5),  # μ21 / m00^2.5
            ]
            
            return central_moments
            
        except Exception:
            return [0.0] * 6


class HuMomentExtractor(BaseFeatureExtractor):
    """
    Simplified extractor that only extracts the 7 Hu moments
    """
    
    def __init__(self, config: Dict[str, Any] = None, **kwargs):
        """
        Initialize Hu moment extractor
        
        Args:
            config: Configuration dictionary with optional parameters:
                   - use_log_transform: Whether to apply log transform (default: True)
            **kwargs: Alternative way to pass configuration parameters directly
        """
        # Merge config dict and kwargs
        if config is None:
            config = {}
        config = {**config, **kwargs}

        super().__init__(config)
        self.use_log_transform = self.config.get('use_log_transform', True)
    
    def extract_features(self, contour: np.ndarray) -> List[float]:
        """
        Extract the 7 Hu moments from contour
        
        Args:
            contour: OpenCV contour array
            
        Returns:
            List of 7 Hu moment features
        """
        try:
            # Calculate moments and Hu moments
            moments = cv2.moments(contour)
            hu_moments = cv2.HuMoments(moments).flatten()
            
            if self.use_log_transform:
                # Apply sign-preserving log transformation
                features = []
                for hu in hu_moments:
                    if hu == 0:
                        features.append(0.0)
                    else:
                        features.append(np.copysign(np.log10(np.abs(hu) + 1e-10), hu))
                return features
            else:
                return hu_moments.tolist()
                
        except Exception as e:
            print(f"Warning: Error extracting Hu moments: {e}")
            return [0.0] * 7
    
    def get_feature_names(self) -> List[str]:
        """Get names of Hu moment features"""
        return [f'hu_moment_{i+1}' for i in range(7)]
    
    def get_feature_count(self) -> int:
        """Get number of Hu moment features"""
        return 7


class ZernikeMomentExtractor(BaseFeatureExtractor):
    """
    Extractor for Zernike moments (orthogonal moments)
    Provides rotation invariant shape descriptors
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Zernike moment extractor
        
        Args:
            config: Configuration dictionary with parameters:
                   - max_order: Maximum order of Zernike moments (default: 8)
                   - radius: Radius for Zernike calculation (default: auto)
        """
        super().__init__(config)
        self.max_order = self.config.get('max_order', 8)
        self.radius = self.config.get('radius', None)
    
    def extract_features(self, contour: np.ndarray) -> List[float]:
        """
        Extract Zernike moments from contour
        
        Args:
            contour: OpenCV contour array
            
        Returns:
            List of Zernike moment features
        """
        try:
            # Create binary image from contour
            x, y, w, h = cv2.boundingRect(contour)
            size = max(w, h)
            
            # Create binary image
            img = np.zeros((size, size), dtype=np.uint8)
            
            # Translate contour to fit in the image
            translated_contour = contour.copy()
            translated_contour[:, 0, 0] -= x - (size - w) // 2
            translated_contour[:, 0, 1] -= y - (size - h) // 2
            
            # Fill contour
            cv2.fillPoly(img, [translated_contour], 255)
            
            # Calculate Zernike moments
            zernike_moments = self._calculate_zernike_moments(img)
            
            return zernike_moments
            
        except Exception as e:
            print(f"Warning: Error extracting Zernike moments: {e}")
            # Return approximate number of features for max_order
            n_features = ((self.max_order + 1) * (self.max_order + 2)) // 2
            return [0.0] * min(n_features, 20)  # Limit to reasonable number
    
    def _calculate_zernike_moments(self, image: np.ndarray) -> List[float]:
        """
        Calculate Zernike moments for binary image
        
        This is a simplified implementation. For production use,
        consider using a dedicated library like mahotas.
        
        Args:
            image: Binary image
            
        Returns:
            List of Zernike moment magnitudes
        """
        # Simplified Zernike calculation
        # In practice, you'd want to use a proper implementation
        
        moments = []
        center = np.array(image.shape) / 2
        
        # Calculate basic radial features as a placeholder
        y, x = np.ogrid[:image.shape[0], :image.shape[1]]
        r = np.sqrt((x - center[1])**2 + (y - center[0])**2)
        theta = np.arctan2(y - center[0], x - center[1])
        
        # Simple radial moments as approximation
        for order in range(0, min(self.max_order + 1, 6), 2):
            for rep in range(order + 1):
                # Simplified radial function
                if image.sum() > 0:
                    moment = np.sum(image * (r ** order) * np.cos(rep * theta)) / image.sum()
                else:
                    moment = 0.0
                moments.append(abs(moment))  # Use magnitude only
        
        return moments[:10]  # Return first 10 features
    
    def get_feature_names(self) -> List[str]:
        """Get names of Zernike moment features"""
        names = []
        count = 0
        for order in range(0, min(self.max_order + 1, 6), 2):
            for rep in range(order + 1):
                names.append(f'zernike_{order}_{rep}')
                count += 1
                if count >= 10:  # Limit to 10 features
                    break
            if count >= 10:
                break
        return names
    
    def get_feature_count(self) -> int:
        """Get number of Zernike moment features"""
        return len(self.get_feature_names())


# Register extractors with factory
from .base_extractor import FeatureExtractorFactory

FeatureExtractorFactory.register_extractor('moment', MomentFeatureExtractor)
FeatureExtractorFactory.register_extractor('hu', HuMomentExtractor)
FeatureExtractorFactory.register_extractor('zernike', ZernikeMomentExtractor)