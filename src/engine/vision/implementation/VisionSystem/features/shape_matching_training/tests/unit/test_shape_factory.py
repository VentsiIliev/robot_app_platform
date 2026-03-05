"""
Unit tests for Shape Factory module
"""

import pytest
import numpy as np
from core.dataset.shape_factory import ShapeFactory, ShapeType


@pytest.mark.unit
class TestShapeFactory:
    """Test cases for the ShapeFactory class."""
    
    def test_generate_circle(self):
        """Test circle generation."""
        contour = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
        
        assert contour is not None
        assert isinstance(contour, np.ndarray)
        assert len(contour.shape) == 3
        assert contour.shape[2] == 2  # x, y coordinates
        assert len(contour) > 10  # Should have reasonable number of points
    
    def test_generate_square(self):
        """Test square generation."""
        contour = ShapeFactory.generate_shape(ShapeType.SQUARE, scale=1.0)
        
        assert contour is not None
        assert isinstance(contour, np.ndarray)
        assert len(contour) >= 4  # At least 4 corners
    
    def test_generate_triangle(self):
        """Test triangle generation."""
        contour = ShapeFactory.generate_shape(ShapeType.TRIANGLE, scale=1.0)
        
        assert contour is not None
        assert isinstance(contour, np.ndarray)
        assert len(contour) >= 3  # At least 3 corners
    
    def test_different_scales(self):
        """Test shape generation with different scales."""
        scale_small = 0.5
        scale_large = 2.0
        
        contour_small = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale_small)
        contour_large = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale_large)
        
        # Both should be valid contours
        assert contour_small is not None
        assert contour_large is not None
        
        # Calculate approximate sizes (using bounding box)
        bbox_small = np.max(contour_small.reshape(-1, 2), axis=0) - np.min(contour_small.reshape(-1, 2), axis=0)
        bbox_large = np.max(contour_large.reshape(-1, 2), axis=0) - np.min(contour_large.reshape(-1, 2), axis=0)
        
        # Large should be bigger than small
        assert np.mean(bbox_large) > np.mean(bbox_small)
    
    def test_different_image_sizes(self):
        """Test shape generation with different image sizes."""
        size_small = (128, 128)
        size_large = (512, 512)
        
        contour_small = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0, img_size=size_small)
        contour_large = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0, img_size=size_large)
        
        assert contour_small is not None
        assert contour_large is not None
        
        # Both should fit within their respective image bounds
        points_small = contour_small.reshape(-1, 2)
        points_large = contour_large.reshape(-1, 2)
        
        assert np.all(points_small >= 0)
        assert np.all(points_small[:, 0] < size_small[0])
        assert np.all(points_small[:, 1] < size_small[1])
        
        assert np.all(points_large >= 0)
        assert np.all(points_large[:, 0] < size_large[0])
        assert np.all(points_large[:, 1] < size_large[1])
    
    def test_all_shape_types(self):
        """Test that all shape types can be generated."""
        for shape_type in ShapeType:
            try:
                contour = ShapeFactory.generate_shape(shape_type, scale=1.0)
                assert contour is not None, f"Failed to generate {shape_type.value}"
                assert len(contour) >= 3, f"{shape_type.value} has too few points"
            except NotImplementedError:
                # Some shapes might not be implemented yet
                pytest.skip(f"{shape_type.value} not implemented")
    
    def test_invalid_scale(self):
        """Test behavior with invalid scale values."""
        with pytest.raises((ValueError, AssertionError)):
            ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=0)
        
        with pytest.raises((ValueError, AssertionError)):
            ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=-1)
    
    def test_get_hard_negative_pairs(self):
        """Test getting hard negative pairs."""
        pairs = ShapeFactory.get_hard_negative_pairs()
        
        assert isinstance(pairs, list)
        assert len(pairs) > 0
        
        for shape1, shape2 in pairs:
            assert isinstance(shape1, ShapeType)
            assert isinstance(shape2, ShapeType)
            assert shape1 != shape2  # Should be different shapes
    
    @pytest.mark.performance
    def test_generation_performance(self, performance_tracker):
        """Test shape generation performance."""
        performance_tracker.start("circle_generation")
        
        for _ in range(100):
            ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
        
        duration = performance_tracker.stop()
        
        # Should generate 100 circles in reasonable time
        performance_tracker.assert_performance("circle_generation", 5.0)
    
    def test_reproducibility(self):
        """Test that shape generation is deterministic with same parameters."""
        # Note: This test assumes the factory uses deterministic generation
        # If randomness is used, this test would need to be modified
        contour1 = ShapeFactory.generate_shape(ShapeType.SQUARE, scale=1.0, img_size=(256, 256))
        contour2 = ShapeFactory.generate_shape(ShapeType.SQUARE, scale=1.0, img_size=(256, 256))
        
        # For basic shapes like squares, should be identical
        np.testing.assert_array_equal(contour1, contour2)
    
    def test_contour_properties(self):
        """Test that generated contours have expected properties."""
        contour = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0)
        
        # Should be a closed contour (first and last points close)
        points = contour.reshape(-1, 2)
        first_point = points[0]
        last_point = points[-1]
        
        # For a properly closed contour, first and last should be close
        # (allowing for some numerical tolerance)
        distance = np.linalg.norm(first_point - last_point)
        assert distance < 5.0  # Reasonable tolerance
        
        # Should have positive area
        import cv2
        area = cv2.contourArea(contour)
        assert area > 0
    
    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        # Very small scale
        contour_tiny = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=0.1)
        assert contour_tiny is not None
        
        # Very large scale (within image bounds)
        contour_large = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=10.0, img_size=(1000, 1000))
        assert contour_large is not None
        
        # Square image
        contour_square = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0, img_size=(256, 256))
        assert contour_square is not None
        
        # Rectangular image
        contour_rect = ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0, img_size=(256, 512))
        assert contour_rect is not None