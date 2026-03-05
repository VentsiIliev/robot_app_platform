"""
Data Augmentation Module

Provides various augmentation techniques for contour data including
rotation, noise addition, deformation, and simplification.
"""

import cv2
import numpy as np
from typing import List, Dict, Any, Optional, Callable
from abc import ABC, abstractmethod
import random


class BaseAugmentation(ABC):
    """Abstract base class for augmentation techniques"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
    
    @abstractmethod
    def apply(self, contour: np.ndarray) -> np.ndarray:
        """
        Apply augmentation to a contour
        
        Args:
            contour: Input contour
            
        Returns:
            Augmented contour
        """
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Get augmentation parameters"""
        pass


class RotationAugmentation(BaseAugmentation):
    """Rotate contour by random or specified angle"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.min_angle = self.config.get('min_angle', 0)
        self.max_angle = self.config.get('max_angle', 360)
        self.fixed_angle = self.config.get('fixed_angle', None)
    
    def apply(self, contour: np.ndarray) -> np.ndarray:
        """Apply rotation to contour"""
        if self.fixed_angle is not None:
            angle = self.fixed_angle
        else:
            angle = random.uniform(self.min_angle, self.max_angle)
        
        return self._rotate_contour(contour, angle)
    
    def _rotate_contour(self, contour: np.ndarray, angle_deg: float) -> np.ndarray:
        """Rotate contour by specified angle in degrees"""
        if len(contour) == 0:
            return contour
        
        # Get contour points
        pts = contour.reshape(-1, 2).astype(np.float32)
        
        # Find centroid
        cx, cy = np.mean(pts, axis=0)
        
        # Create rotation matrix
        angle_rad = np.deg2rad(angle_deg)
        cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
        rotation_matrix = np.array([[cos_a, -sin_a], [sin_a, cos_a]], dtype=np.float32)
        
        # Translate to origin, rotate, translate back
        centered = pts - [cx, cy]
        rotated = np.dot(centered, rotation_matrix.T)
        final_points = rotated + [cx, cy]
        
        return final_points.reshape(-1, 1, 2).astype(np.int32)
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'min_angle': self.min_angle,
            'max_angle': self.max_angle,
            'fixed_angle': self.fixed_angle
        }


class NoiseAugmentation(BaseAugmentation):
    """Add Gaussian noise to contour points"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.noise_level = self.config.get('noise_level', 0.2)
        self.noise_type = self.config.get('noise_type', 'gaussian')
    
    def apply(self, contour: np.ndarray) -> np.ndarray:
        """Apply noise to contour"""
        if len(contour) == 0:
            return contour
        
        pts = contour.reshape(-1, 2).astype(np.float32)
        
        if self.noise_type == 'gaussian':
            noise = np.random.normal(0, self.noise_level, pts.shape)
        elif self.noise_type == 'uniform':
            noise = np.random.uniform(-self.noise_level, self.noise_level, pts.shape)
        else:
            raise ValueError(f"Unknown noise type: {self.noise_type}")
        
        noisy_pts = pts + noise
        return noisy_pts.reshape(-1, 1, 2).astype(np.int32)
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'noise_level': self.noise_level,
            'noise_type': self.noise_type
        }


class DeformationAugmentation(BaseAugmentation):
    """Apply random deformation to contour"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.deform_strength = self.config.get('deform_strength', 0.01)
        self.deform_type = self.config.get('deform_type', 'random')
    
    def apply(self, contour: np.ndarray) -> np.ndarray:
        """Apply deformation to contour"""
        if len(contour) == 0:
            return contour
        
        pts = contour.reshape(-1, 2).astype(np.float32)
        
        if self.deform_type == 'random':
            # Random displacement for each point
            deformation = np.random.randn(*pts.shape) * self.deform_strength * 100
        elif self.deform_type == 'wave':
            # Sinusoidal wave deformation
            n_points = len(pts)
            wave_freq = self.config.get('wave_frequency', 0.1)
            phase = np.linspace(0, 2*np.pi*wave_freq*n_points, n_points)
            wave_x = np.sin(phase) * self.deform_strength * 50
            wave_y = np.cos(phase * 0.7) * self.deform_strength * 50
            deformation = np.column_stack([wave_x, wave_y])
        else:
            raise ValueError(f"Unknown deformation type: {self.deform_type}")
        
        deformed_pts = pts + deformation
        return deformed_pts.reshape(-1, 1, 2).astype(np.int32)
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'deform_strength': self.deform_strength,
            'deform_type': self.deform_type
        }


class SimplificationAugmentation(BaseAugmentation):
    """Simplify contour using Douglas-Peucker algorithm"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.epsilon_ratio = self.config.get('epsilon_ratio', 0.01)
        self.adaptive = self.config.get('adaptive', True)
    
    def apply(self, contour: np.ndarray) -> np.ndarray:
        """Apply simplification to contour"""
        if len(contour) < 3:
            return contour
        
        try:
            if self.adaptive:
                # Adaptive epsilon based on contour perimeter
                perimeter = cv2.arcLength(contour, True)
                epsilon = self.epsilon_ratio * perimeter
            else:
                # Fixed epsilon
                epsilon = self.epsilon_ratio * 100  # Fixed value
            
            simplified = cv2.approxPolyDP(contour, epsilon, True)
            
            # Ensure we have at least 3 points
            if len(simplified) < 3:
                return contour
            
            return simplified
        except:
            return contour
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'epsilon_ratio': self.epsilon_ratio,
            'adaptive': self.adaptive
        }


class ScaleAugmentation(BaseAugmentation):
    """Scale contour by a random or specified factor"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.min_scale = self.config.get('min_scale', 0.8)
        self.max_scale = self.config.get('max_scale', 1.2)
        self.fixed_scale = self.config.get('fixed_scale', None)
    
    def apply(self, contour: np.ndarray) -> np.ndarray:
        """Apply scaling to contour"""
        if len(contour) == 0:
            return contour
        
        if self.fixed_scale is not None:
            scale_factor = self.fixed_scale
        else:
            scale_factor = random.uniform(self.min_scale, self.max_scale)
        
        pts = contour.reshape(-1, 2).astype(np.float32)
        
        # Find centroid
        cx, cy = np.mean(pts, axis=0)
        
        # Scale around centroid
        centered = pts - [cx, cy]
        scaled = centered * scale_factor
        final_points = scaled + [cx, cy]
        
        return final_points.reshape(-1, 1, 2).astype(np.int32)
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'min_scale': self.min_scale,
            'max_scale': self.max_scale,
            'fixed_scale': self.fixed_scale
        }


class ElasticDeformationAugmentation(BaseAugmentation):
    """Apply elastic deformation to contour"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.alpha = self.config.get('alpha', 1.0)
        self.sigma = self.config.get('sigma', 0.1)
    
    def apply(self, contour: np.ndarray) -> np.ndarray:
        """Apply elastic deformation"""
        if len(contour) < 3:
            return contour
        
        pts = contour.reshape(-1, 2).astype(np.float32)
        n_points = len(pts)
        
        # Generate smooth random displacement fields
        dx = np.random.randn(n_points) * self.sigma
        dy = np.random.randn(n_points) * self.sigma
        
        # Smooth the displacement fields
        if n_points > 5:
            dx = self._smooth_1d(dx)
            dy = self._smooth_1d(dy)
        
        # Apply deformation
        displacement = np.column_stack([dx, dy]) * self.alpha
        deformed_pts = pts + displacement
        
        return deformed_pts.reshape(-1, 1, 2).astype(np.int32)
    
    def _smooth_1d(self, signal: np.ndarray, window_size: int = 5) -> np.ndarray:
        """Apply simple moving average smoothing"""
        if len(signal) < window_size:
            return signal
        
        # Pad signal for circular convolution
        pad_size = window_size // 2
        padded = np.pad(signal, pad_size, mode='wrap')
        
        # Apply moving average
        kernel = np.ones(window_size) / window_size
        smoothed = np.convolve(padded, kernel, mode='valid')
        
        return smoothed
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'alpha': self.alpha,
            'sigma': self.sigma
        }


class ContourAugmenter:
    """
    Main augmentation coordinator that applies multiple augmentations
    to contours with configurable pipelines.
    """
    
    def __init__(self, augmentation_config: Optional[Dict[str, Any]] = None):
        """
        Initialize contour augmenter
        
        Args:
            augmentation_config: Configuration for augmentations
        """
        self.config = augmentation_config or {}
        self.augmentations = self._build_augmentation_pipeline()
    
    def _build_augmentation_pipeline(self) -> List[BaseAugmentation]:
        """Build augmentation pipeline from configuration"""
        pipeline = []
        
        # Default augmentations if no config provided
        if not self.config:
            pipeline.extend([
                RotationAugmentation({'min_angle': 0, 'max_angle': 360}),
                NoiseAugmentation({'noise_level': 0.2}),
                DeformationAugmentation({'deform_strength': 0.01})
            ])
            return pipeline
        
        # Build from configuration
        for aug_config in self.config.get('augmentations', []):
            aug_type = aug_config['type']
            aug_params = aug_config.get('params', {})
            
            if aug_type == 'rotation':
                pipeline.append(RotationAugmentation(aug_params))
            elif aug_type == 'noise':
                pipeline.append(NoiseAugmentation(aug_params))
            elif aug_type == 'deformation':
                pipeline.append(DeformationAugmentation(aug_params))
            elif aug_type == 'simplification':
                pipeline.append(SimplificationAugmentation(aug_params))
            elif aug_type == 'scale':
                pipeline.append(ScaleAugmentation(aug_params))
            elif aug_type == 'elastic':
                pipeline.append(ElasticDeformationAugmentation(aug_params))
            else:
                print(f"Warning: Unknown augmentation type: {aug_type}")
        
        return pipeline
    
    def augment_contour(self, contour: np.ndarray, 
                       augmentations: Optional[List[str]] = None) -> np.ndarray:
        """
        Apply augmentations to a single contour
        
        Args:
            contour: Input contour
            augmentations: List of augmentation names to apply (None = all)
            
        Returns:
            Augmented contour
        """
        if len(contour) == 0:
            return contour
        
        result = contour.copy()
        
        for augmentation in self.augmentations:
            # Apply augmentation if it's in the requested list or no list provided
            aug_name = augmentation.__class__.__name__.replace('Augmentation', '').lower()
            if augmentations is None or aug_name in augmentations:
                try:
                    result = augmentation.apply(result)
                except Exception as e:
                    print(f"Warning: Augmentation {aug_name} failed: {e}")
                    continue
        
        return result
    
    def create_variants(self, contour: np.ndarray, 
                       n_variants: int = 5,
                       variant_types: Optional[List[str]] = None) -> List[np.ndarray]:
        """
        Create multiple variants of a contour
        
        Args:
            contour: Base contour
            n_variants: Number of variants to create
            variant_types: Types of variants to create
            
        Returns:
            List of variant contours
        """
        variants = []
        
        for i in range(n_variants):
            # Apply different combinations of augmentations
            if variant_types:
                augmentations = variant_types
            else:
                # Randomly select augmentations for variety
                available = ['rotation', 'noise', 'deformation']
                num_augs = random.randint(1, len(available))
                augmentations = random.sample(available, num_augs)
            
            variant = self.augment_contour(contour, augmentations)
            variants.append(variant)
        
        return variants
    
    def get_augmentation_info(self) -> Dict[str, Any]:
        """Get information about configured augmentations"""
        info = {
            'n_augmentations': len(self.augmentations),
            'augmentations': []
        }
        
        for aug in self.augmentations:
            aug_info = {
                'type': aug.__class__.__name__,
                'parameters': aug.get_parameters()
            }
            info['augmentations'].append(aug_info)
        
        return info


# Utility functions for common augmentation patterns
def create_rotation_variants(contour: np.ndarray, 
                           n_variants: int = 6) -> List[np.ndarray]:
    """Create rotation variants of a contour"""
    augmenter = ContourAugmenter()
    variants = []
    
    angle_step = 360 / n_variants
    for i in range(n_variants):
        angle = i * angle_step
        rotation = RotationAugmentation({'fixed_angle': angle})
        variant = rotation.apply(contour)
        variants.append(variant)
    
    return variants


def create_noisy_variants(contour: np.ndarray, 
                        n_variants: int = 4,
                        noise_levels: Optional[List[float]] = None) -> List[np.ndarray]:
    """Create noisy variants of a contour"""
    if noise_levels is None:
        noise_levels = [0.1, 0.2, 0.3, 0.5]
    
    variants = []
    for i in range(n_variants):
        noise_level = noise_levels[i % len(noise_levels)]
        noise_aug = NoiseAugmentation({'noise_level': noise_level})
        variant = noise_aug.apply(contour)
        variants.append(variant)
    
    return variants