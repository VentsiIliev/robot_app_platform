"""
Synthetic Dataset Generation Module

Provides comprehensive synthetic dataset generation for shape similarity training
with configurable parameters and augmentation pipelines.
"""

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
import numpy as np

from .shape_factory import ShapeFactory, ShapeType
from .data_augmentation import ContourAugmenter


@dataclass
class SyntheticContour:
    """Container for synthetic contour with metadata"""
    contour: np.ndarray
    object_id: str
    shape_type: ShapeType
    scale: float
    variant_name: str
    parameters: Dict[str, Any]


class SyntheticDataset:
    """
    Generates synthetic datasets of contours with controlled variations
    for training shape similarity models.
    """
    
    def __init__(self,
                 n_shapes: int = 8,
                 n_scales: int = 3, 
                 n_variants: int = 5,
                 n_noisy: int = 4,
                 shape_types: Optional[List[ShapeType]] = None,
                 img_size: Tuple[int, int] = (256, 256),
                 scale_range: Tuple[float, float] = (0.5, 3.0),
                 include_hard_negatives: bool = True):
        """
        Initialize synthetic dataset generator
        
        Args:
            n_shapes: Number of different shape types to use
            n_scales: Number of different scales per shape
            n_variants: Number of rotation variants per scale
            n_noisy: Number of noise variants per rotation
            shape_types: Specific shape types to use (None = auto-select)
            img_size: Size of image canvas
            scale_range: Min and max scale factors
            include_hard_negatives: Whether to ensure hard negative pairs are included
        """
        self.n_shapes = n_shapes
        self.n_scales = n_scales
        self.n_variants = n_variants
        self.n_noisy = n_noisy
        self.img_size = img_size
        self.scale_range = scale_range
        self.include_hard_negatives = include_hard_negatives
        
        # Select shape types
        if shape_types is None:
            available_shapes = self._get_available_shapes()
            if self.include_hard_negatives:
                # Ensure we have some hard negative pairs
                hard_negative_pairs = ShapeFactory.get_hard_negative_pairs()
                selected_shapes = []
                
                # Add some hard negative pairs
                for shape1, shape2 in hard_negative_pairs[:n_shapes//3]:
                    if len(selected_shapes) < n_shapes:
                        if shape1 not in selected_shapes:
                            selected_shapes.append(shape1)
                        if shape2 not in selected_shapes and len(selected_shapes) < n_shapes:
                            selected_shapes.append(shape2)
                
                # Fill remaining slots randomly
                remaining_shapes = [s for s in available_shapes if s not in selected_shapes]
                while len(selected_shapes) < n_shapes and remaining_shapes:
                    selected_shapes.append(remaining_shapes.pop(random.randint(0, len(remaining_shapes)-1)))
                
                self.shape_types = selected_shapes[:n_shapes]
            else:
                self.shape_types = random.sample(available_shapes, min(n_shapes, len(available_shapes)))
        else:
            self.shape_types = shape_types[:n_shapes]
        
        # Initialize augmenter
        self.augmenter = ContourAugmenter()
        
        print(f"📊 Dataset config: {n_shapes} shapes, {n_scales} scales, {n_variants} variants, {n_noisy} noise levels")
        print(f"🎯 Selected shapes: {[s.value for s in self.shape_types]}")
    
    def generate(self) -> List[SyntheticContour]:
        """
        Generate the complete synthetic dataset
        
        Returns:
            List of synthetic contours with metadata
        """
        print("🔄 Generating synthetic contour dataset...")
        
        contours = []
        total_expected = len(self.shape_types) * self.n_scales * self.n_variants * self.n_noisy
        
        for shape_type in self.shape_types:
            for scale_idx in range(self.n_scales):
                # Calculate scale factor
                scale_factor = self._get_scale_factor(scale_idx)
                
                # Create object ID for this shape+scale combination
                object_id = f"{shape_type.value}_scale{scale_idx}"
                
                for variant_idx in range(self.n_variants):
                    # Generate base contour
                    base_contour = ShapeFactory.generate_shape(
                        shape_type, scale_factor, self.img_size
                    )
                    
                    # Apply rotation variant
                    rotated_contour = self._apply_rotation_variant(base_contour, variant_idx)
                    
                    for noise_idx in range(self.n_noisy):
                        # Apply noise variant
                        final_contour = self._apply_noise_variant(rotated_contour, noise_idx)
                        
                        # Create variant name
                        variant_name = f"rot{variant_idx}_noise{noise_idx}"
                        
                        # Create synthetic contour object
                        synthetic_contour = SyntheticContour(
                            contour=final_contour,
                            object_id=object_id,
                            shape_type=shape_type,
                            scale=scale_factor,
                            variant_name=variant_name,
                            parameters={
                                'scale_idx': scale_idx,
                                'variant_idx': variant_idx,
                                'noise_idx': noise_idx,
                                'rotation_applied': True,
                                'noise_applied': noise_idx > 0
                            }
                        )
                        
                        contours.append(synthetic_contour)
        
        print(f"✅ Generated {len(contours)} contours (expected: {total_expected})")
        return contours
    
    def generate_shape_variants(self, 
                              shape_type: ShapeType, 
                              n_variants: int = 10) -> List[SyntheticContour]:
        """
        Generate multiple variants of a specific shape
        
        Args:
            shape_type: Type of shape to generate
            n_variants: Number of variants to create
            
        Returns:
            List of shape variants
        """
        variants = []
        
        for i in range(n_variants):
            # Random scale within range
            scale = random.uniform(*self.scale_range)
            
            # Generate base contour
            base_contour = ShapeFactory.generate_shape(shape_type, scale, self.img_size)
            
            # Apply random augmentations
            augmented_contour = self.augmenter.augment_contour(base_contour)
            
            synthetic_contour = SyntheticContour(
                contour=augmented_contour,
                object_id=f"{shape_type.value}_variant{i}",
                shape_type=shape_type,
                scale=scale,
                variant_name=f"variant_{i}",
                parameters={'variant_index': i, 'random_augmentation': True}
            )
            
            variants.append(synthetic_contour)
        
        return variants
    
    def _get_available_shapes(self) -> List[ShapeType]:
        """Get list of available shape types"""
        # Return shapes that are implemented in the factory
        implemented_shapes = [
            ShapeType.CIRCLE, ShapeType.ELLIPSE, ShapeType.RECTANGLE, 
            ShapeType.SQUARE, ShapeType.TRIANGLE, ShapeType.DIAMOND,
            ShapeType.PENTAGON, ShapeType.HEXAGON, ShapeType.OCTAGON,
            ShapeType.STAR, ShapeType.HEART
        ]
        return implemented_shapes
    
    def _get_scale_factor(self, scale_idx: int) -> float:
        """Calculate scale factor for given scale index"""
        if self.n_scales == 1:
            return 1.0
        
        min_scale, max_scale = self.scale_range
        scale_step = (max_scale - min_scale) / (self.n_scales - 1)
        return min_scale + scale_idx * scale_step
    
    def _apply_rotation_variant(self, contour: np.ndarray, variant_idx: int) -> np.ndarray:
        """Apply rotation variant based on variant index"""
        if variant_idx == 0:
            return contour  # No rotation for first variant
        
        # Random rotation for other variants
        angle = random.uniform(0, 360)
        return self._rotate_contour(contour, angle)
    
    def _apply_noise_variant(self, contour: np.ndarray, noise_idx: int) -> np.ndarray:
        """Apply noise variant based on noise index"""
        if noise_idx == 0:
            return contour  # No noise for first variant
        
        # Different noise types based on index
        if noise_idx == 1:
            # Light jitter
            return self._jitter_contour(contour, 0.1)
        elif noise_idx == 2:
            # Medium jitter
            return self._jitter_contour(contour, 0.2)
        elif noise_idx == 3:
            # Deformation
            return self._deform_contour(contour, 0.01)
        else:
            # Simplification
            return self._simplify_contour(contour, 0.01)
    
    def _rotate_contour(self, contour: np.ndarray, angle_deg: float) -> np.ndarray:
        """Rotate contour by specified angle"""
        if len(contour) == 0:
            return contour
        
        pts = contour.reshape(-1, 2).astype(np.float32)
        cx, cy = np.mean(pts, axis=0)
        
        rad = np.deg2rad(angle_deg)
        cos_a, sin_a = np.cos(rad), np.sin(rad)
        rotation_matrix = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
        
        centered = pts - [cx, cy]
        rotated = np.dot(centered, rotation_matrix.T)
        final_points = rotated + [cx, cy]
        
        return final_points.reshape(-1, 1, 2).astype(np.int32)
    
    def _jitter_contour(self, contour: np.ndarray, noise_level: float = 0.2) -> np.ndarray:
        """Add random jitter to contour points"""
        if len(contour) == 0:
            return contour
        
        pts = contour.reshape(-1, 2).astype(np.float32)
        noise = np.random.normal(0, noise_level, pts.shape)
        jittered = pts + noise
        
        return jittered.reshape(-1, 1, 2).astype(np.int32)
    
    def _deform_contour(self, contour: np.ndarray, strength: float = 0.01) -> np.ndarray:
        """Apply random deformation to contour"""
        if len(contour) == 0:
            return contour
        
        pts = contour.reshape(-1, 2).astype(np.float32)
        deformation = np.random.randn(*pts.shape) * strength * 100
        deformed = pts + deformation
        
        return deformed.reshape(-1, 1, 2).astype(np.int32)
    
    def _simplify_contour(self, contour: np.ndarray, epsilon_ratio: float = 0.01) -> np.ndarray:
        """Simplify contour using Douglas-Peucker algorithm"""
        import cv2
        
        if len(contour) < 3:
            return contour
        
        try:
            epsilon = epsilon_ratio * cv2.arcLength(contour, True)
            simplified = cv2.approxPolyDP(contour, epsilon, True)
            
            # Ensure we have at least 3 points
            if len(simplified) < 3:
                return contour
            
            return simplified
        except:
            return contour
    
    def get_dataset_statistics(self, contours: List[SyntheticContour]) -> Dict[str, Any]:
        """Get statistics about the generated dataset"""
        stats = {
            'total_contours': len(contours),
            'shape_distribution': {},
            'scale_distribution': {},
            'object_id_count': len(set(c.object_id for c in contours)),
            'avg_contour_points': 0,
            'contour_areas': []
        }
        
        # Shape type distribution
        for contour in contours:
            shape_name = contour.shape_type.value
            stats['shape_distribution'][shape_name] = stats['shape_distribution'].get(shape_name, 0) + 1
        
        # Scale distribution
        for contour in contours:
            scale_key = f"scale_{contour.parameters.get('scale_idx', 0)}"
            stats['scale_distribution'][scale_key] = stats['scale_distribution'].get(scale_key, 0) + 1
        
        # Contour statistics
        if contours:
            import cv2
            point_counts = [len(c.contour) for c in contours]
            areas = [cv2.contourArea(c.contour) for c in contours]
            
            stats['avg_contour_points'] = np.mean(point_counts)
            stats['contour_areas'] = {
                'mean': np.mean(areas),
                'std': np.std(areas),
                'min': np.min(areas),
                'max': np.max(areas)
            }
        
        return stats
    
    def save_dataset(self, contours: List[SyntheticContour], filepath: str):
        """Save dataset to file"""
        import pickle
        from pathlib import Path
        
        filepath = Path(filepath)
        
        # Prepare data for saving
        save_data = {
            'contours': contours,
            'config': {
                'n_shapes': self.n_shapes,
                'n_scales': self.n_scales,
                'n_variants': self.n_variants,
                'n_noisy': self.n_noisy,
                'shape_types': [s.value for s in self.shape_types],
                'img_size': self.img_size,
                'scale_range': self.scale_range,
                'include_hard_negatives': self.include_hard_negatives
            },
            'statistics': self.get_dataset_statistics(contours)
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(save_data, f)
        
        print(f"💾 Dataset saved: {filepath}")
    
    @classmethod
    def load_dataset(cls, filepath: str) -> Tuple['SyntheticDataset', List[SyntheticContour]]:
        """Load dataset from file"""
        import pickle
        from pathlib import Path
        
        filepath = Path(filepath)
        
        with open(filepath, 'rb') as f:
            save_data = pickle.load(f)
        
        # Reconstruct dataset generator
        config = save_data['config']
        shape_types = [ShapeType(s) for s in config['shape_types']]
        
        dataset = cls(
            n_shapes=config['n_shapes'],
            n_scales=config['n_scales'],
            n_variants=config['n_variants'],
            n_noisy=config['n_noisy'],
            shape_types=shape_types,
            img_size=tuple(config['img_size']),
            scale_range=tuple(config['scale_range']),
            include_hard_negatives=config['include_hard_negatives']
        )
        
        contours = save_data['contours']
        
        print(f"📂 Dataset loaded: {len(contours)} contours from {filepath}")
        
        return dataset, contours