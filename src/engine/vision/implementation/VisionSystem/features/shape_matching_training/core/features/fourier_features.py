"""
Fourier-Based Feature Extractor

Extracts Fourier descriptors and frequency domain features from contours,
providing rotation and translation invariant shape descriptors.
"""

import cv2
import numpy as np
from typing import List, Dict, Any
from .base_extractor import BaseFeatureExtractor


class FourierFeatureExtractor(BaseFeatureExtractor):
    """
    Extracts Fourier descriptors from contours using FFT analysis
    of the contour boundary representation.
    """
    
    def __init__(self, config: Dict[str, Any] = None, **kwargs):
        """
        Initialize Fourier feature extractor
        
        Args:
            config: Configuration dictionary with parameters:
                   - n_descriptors: Number of Fourier descriptors to extract (default: 4)
                   - normalize: Whether to normalize descriptors (default: True)
                   - use_magnitude_only: Use only magnitude, ignore phase (default: True)
            **kwargs: Alternative way to pass configuration parameters directly
        """
        # Merge config dict and kwargs
        if config is None:
            config = {}
        config = {**config, **kwargs}

        super().__init__(config)
        self.n_descriptors = self.config.get('n_descriptors', 4)
        self.normalize = self.config.get('normalize', True)
        self.use_magnitude_only = self.config.get('use_magnitude_only', True)
    
    def extract_features(self, contour: np.ndarray) -> List[float]:
        """
        Extract Fourier descriptors from contour
        
        Args:
            contour: OpenCV contour array
            
        Returns:
            List of Fourier descriptor features
        """
        try:
            # Calculate Fourier descriptors
            descriptors = self._fourier_descriptors(contour)
            return descriptors
            
        except Exception as e:
            print(f"Warning: Error extracting Fourier features: {e}")
            return [0.0] * self.n_descriptors
    
    def get_feature_names(self) -> List[str]:
        """Get names of Fourier descriptor features"""
        return [f'fourier_desc_{i+1}' for i in range(self.n_descriptors)]
    
    def get_feature_count(self) -> int:
        """Get number of Fourier descriptor features"""
        return self.n_descriptors
    
    def _fourier_descriptors(self, contour: np.ndarray) -> List[float]:
        """
        Calculate Fourier descriptors for a contour
        
        Args:
            contour: OpenCV contour array
            
        Returns:
            List of Fourier descriptors
        """
        # Ensure contour has enough points
        if len(contour) < 3:
            return [0.0] * self.n_descriptors
        
        # Convert contour to complex representation
        # Each point (x, y) becomes x + iy
        contour_points = contour.reshape(-1, 2)
        contour_complex = contour_points[:, 0] + 1j * contour_points[:, 1]
        
        # Apply FFT
        fft = np.fft.fft(contour_complex)
        
        # Extract descriptors (skip DC component)
        if len(fft) <= 1:
            return [0.0] * self.n_descriptors
        
        # Get the requested number of descriptors
        n_to_extract = min(self.n_descriptors, len(fft) - 1)
        
        if self.normalize and np.abs(fft[1]) > 1e-10:
            # Normalize by first harmonic for scale invariance
            descriptors = np.abs(fft[1:n_to_extract+1]) / np.abs(fft[1])
        else:
            # Use raw magnitudes
            descriptors = np.abs(fft[1:n_to_extract+1])
        
        # Pad with zeros if needed
        result = descriptors.tolist()
        while len(result) < self.n_descriptors:
            result.append(0.0)
        
        return result[:self.n_descriptors]


class CurvatureFeatureExtractor(BaseFeatureExtractor):
    """
    Extracts curvature-based features from contours including
    curvature histograms and curvature statistics.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize curvature feature extractor
        
        Args:
            config: Configuration dictionary with parameters:
                   - n_bins: Number of bins for curvature histogram (default: 16)
                   - window_size: Window size for curvature calculation (default: 5)
                   - normalize_histogram: Whether to normalize histogram (default: True)
        """
        super().__init__(config)
        self.n_bins = self.config.get('n_bins', 16)
        self.window_size = self.config.get('window_size', 5)
        self.normalize_histogram = self.config.get('normalize_histogram', True)
    
    def extract_features(self, contour: np.ndarray) -> List[float]:
        """
        Extract curvature-based features from contour
        
        Args:
            contour: OpenCV contour array
            
        Returns:
            List of curvature features (histogram + statistics)
        """
        try:
            # Calculate curvature along the contour
            curvatures = self._calculate_curvature(contour)
            
            # Create curvature histogram
            histogram = self._curvature_histogram(curvatures)
            
            # Calculate curvature statistics
            stats = self._curvature_statistics(curvatures)
            
            features = histogram + stats
            return features
            
        except Exception as e:
            print(f"Warning: Error extracting curvature features: {e}")
            # Return zeros: histogram bins + 4 statistics
            return [0.0] * (self.n_bins + 4)
    
    def get_feature_names(self) -> List[str]:
        """Get names of curvature features"""
        names = [f'curvature_bin_{i+1}' for i in range(self.n_bins)]
        names.extend(['curvature_mean', 'curvature_std', 'curvature_max', 'curvature_min'])
        return names
    
    def get_feature_count(self) -> int:
        """Get number of curvature features"""
        return self.n_bins + 4  # histogram + statistics
    
    def _calculate_curvature(self, contour: np.ndarray) -> np.ndarray:
        """
        Calculate curvature at each point along the contour
        
        Args:
            contour: OpenCV contour array
            
        Returns:
            Array of curvature values
        """
        if len(contour) < self.window_size * 2:
            return np.array([0.0])
        
        # Reshape contour to (N, 2)
        points = contour.reshape(-1, 2).astype(np.float64)
        n_points = len(points)
        
        curvatures = []
        
        for i in range(n_points):
            # Get points in a window around current point
            start_idx = (i - self.window_size) % n_points
            end_idx = (i + self.window_size) % n_points
            
            # Calculate curvature using finite differences
            if start_idx < end_idx:
                window_points = points[start_idx:end_idx+1]
            else:
                # Handle wrap-around
                window_points = np.vstack([points[start_idx:], points[:end_idx+1]])
            
            if len(window_points) >= 3:
                curvature = self._point_curvature(window_points)
                curvatures.append(curvature)
            else:
                curvatures.append(0.0)
        
        return np.array(curvatures)
    
    def _point_curvature(self, points: np.ndarray) -> float:
        """
        Calculate curvature for a point given surrounding points
        
        Args:
            points: Array of points in neighborhood
            
        Returns:
            Curvature value
        """
        if len(points) < 3:
            return 0.0
        
        try:
            # Use central point and its neighbors
            center_idx = len(points) // 2
            if center_idx == 0 or center_idx == len(points) - 1:
                return 0.0
            
            p1 = points[center_idx - 1]
            p2 = points[center_idx]
            p3 = points[center_idx + 1]
            
            # Calculate vectors
            v1 = p2 - p1
            v2 = p3 - p2
            
            # Calculate curvature using cross product and magnitudes
            cross_product = v1[0] * v2[1] - v1[1] * v2[0]
            
            v1_mag = np.linalg.norm(v1)
            v2_mag = np.linalg.norm(v2)
            
            if v1_mag == 0 or v2_mag == 0:
                return 0.0
            
            # Curvature formula
            curvature = cross_product / (v1_mag * v2_mag * (v1_mag + v2_mag))
            
            return curvature
            
        except Exception:
            return 0.0
    
    def _curvature_histogram(self, curvatures: np.ndarray) -> List[float]:
        """
        Create histogram of curvature values
        
        Args:
            curvatures: Array of curvature values
            
        Returns:
            Histogram as list
        """
        if len(curvatures) == 0:
            return [0.0] * self.n_bins
        
        try:
            # Remove outliers for better histogram
            q75, q25 = np.percentile(curvatures, [75, 25])
            iqr = q75 - q25
            lower_bound = q25 - 1.5 * iqr
            upper_bound = q75 + 1.5 * iqr
            
            filtered_curvatures = curvatures[
                (curvatures >= lower_bound) & (curvatures <= upper_bound)
            ]
            
            if len(filtered_curvatures) == 0:
                filtered_curvatures = curvatures
            
            # Create histogram
            hist, _ = np.histogram(filtered_curvatures, bins=self.n_bins)
            
            # Normalize if requested
            if self.normalize_histogram and hist.sum() > 0:
                hist = hist.astype(float) / hist.sum()
            
            return hist.tolist()
            
        except Exception:
            return [0.0] * self.n_bins
    
    def _curvature_statistics(self, curvatures: np.ndarray) -> List[float]:
        """
        Calculate statistical features of curvature
        
        Args:
            curvatures: Array of curvature values
            
        Returns:
            List of statistics [mean, std, max, min]
        """
        if len(curvatures) == 0:
            return [0.0, 0.0, 0.0, 0.0]
        
        try:
            stats = [
                np.mean(curvatures),
                np.std(curvatures),
                np.max(curvatures),
                np.min(curvatures)
            ]
            
            # Handle potential NaN values
            stats = [0.0 if np.isnan(s) else s for s in stats]
            
            return stats
            
        except Exception:
            return [0.0, 0.0, 0.0, 0.0]


class SpectralFeatureExtractor(BaseFeatureExtractor):
    """
    Extracts spectral features from contour using power spectrum analysis
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize spectral feature extractor
        
        Args:
            config: Configuration dictionary with parameters:
                   - n_frequencies: Number of frequency components (default: 8)
                   - use_log_power: Whether to use log power spectrum (default: True)
        """
        super().__init__(config)
        self.n_frequencies = self.config.get('n_frequencies', 8)
        self.use_log_power = self.config.get('use_log_power', True)
    
    def extract_features(self, contour: np.ndarray) -> List[float]:
        """
        Extract spectral features from contour
        
        Args:
            contour: OpenCV contour array
            
        Returns:
            List of spectral features
        """
        try:
            # Convert to complex signal
            points = contour.reshape(-1, 2)
            signal = points[:, 0] + 1j * points[:, 1]
            
            # Calculate power spectrum
            fft = np.fft.fft(signal)
            power_spectrum = np.abs(fft) ** 2
            
            # Take low-frequency components
            n_to_take = min(self.n_frequencies, len(power_spectrum) // 2)
            features = power_spectrum[1:n_to_take+1]  # Skip DC component
            
            if self.use_log_power:
                features = np.log(features + 1e-10)  # Add small epsilon to avoid log(0)
            
            # Pad if necessary
            result = features.tolist()
            while len(result) < self.n_frequencies:
                result.append(0.0)
            
            return result[:self.n_frequencies]
            
        except Exception as e:
            print(f"Warning: Error extracting spectral features: {e}")
            return [0.0] * self.n_frequencies
    
    def get_feature_names(self) -> List[str]:
        """Get names of spectral features"""
        return [f'spectral_freq_{i+1}' for i in range(self.n_frequencies)]
    
    def get_feature_count(self) -> int:
        """Get number of spectral features"""
        return self.n_frequencies


# Register extractors with factory
from .base_extractor import FeatureExtractorFactory

FeatureExtractorFactory.register_extractor('fourier', FourierFeatureExtractor)
FeatureExtractorFactory.register_extractor('curvature', CurvatureFeatureExtractor)
FeatureExtractorFactory.register_extractor('spectral', SpectralFeatureExtractor)