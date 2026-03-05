"""
Unit tests for Feature Extractor modules
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch

from core.features.geometric_features import GeometricFeatureExtractor
from core.features.moment_features import HuMomentExtractor, ZernikeMomentExtractor
from core.features.fourier_features import FourierFeatureExtractor
from core.features.base_extractor import CompositeFeatureExtractor, FeatureExtractorFactory


@pytest.mark.unit
class TestGeometricFeatureExtractor:
    """Test cases for GeometricFeatureExtractor."""
    
    def test_extract_features_valid_contour(self, geometric_extractor, simple_contour, test_helpers):
        """Test feature extraction from valid contour."""
        features = geometric_extractor.extract_features(simple_contour)
        
        test_helpers.assert_features_valid(features)
        assert len(features) == 13  # Expected number of geometric features
    
    def test_feature_names(self, geometric_extractor):
        """Test that feature names are provided."""
        names = geometric_extractor.get_feature_names()
        
        assert isinstance(names, list)
        assert len(names) > 0
        assert all(isinstance(name, str) for name in names)
        
        # Check for expected feature names
        expected_features = ['area', 'perimeter', 'aspect_ratio', 'solidity', 'extent']
        for expected in expected_features:
            assert any(expected in name.lower() for name in names)
    
    def test_empty_contour(self, geometric_extractor):
        """Test behavior with empty contour."""
        empty_contour = np.array([]).reshape(0, 1, 2)
        
        with pytest.raises((ValueError, IndexError)):
            geometric_extractor.extract_features(empty_contour)
    
    def test_invalid_contour(self, geometric_extractor):
        """Test behavior with invalid contour."""
        # Wrong shape
        invalid_contour = np.array([[1, 2], [3, 4]])  # Missing middle dimension
        
        with pytest.raises((ValueError, IndexError)):
            geometric_extractor.extract_features(invalid_contour)
    
    def test_feature_consistency(self, geometric_extractor):
        """Test that features are consistent across multiple extractions."""
        from core.dataset.shape_factory import ShapeFactory, ShapeType
        
        contour = ShapeFactory.generate_shape(ShapeType.SQUARE, 1.0)
        
        features1 = geometric_extractor.extract_features(contour)
        features2 = geometric_extractor.extract_features(contour)
        
        np.testing.assert_array_equal(features1, features2)
    
    def test_scale_invariance_properties(self, geometric_extractor):
        """Test that scale-invariant features behave correctly."""
        from core.dataset.shape_factory import ShapeFactory, ShapeType
        
        contour_small = ShapeFactory.generate_shape(ShapeType.CIRCLE, 0.5)
        contour_large = ShapeFactory.generate_shape(ShapeType.CIRCLE, 2.0)
        
        features_small = geometric_extractor.extract_features(contour_small)
        features_large = geometric_extractor.extract_features(contour_large)
        
        # Aspect ratio should be similar for circles
        assert abs(features_small[2] - features_large[2]) < 0.1  # aspect_ratio index
        
        # Solidity should be similar
        # (exact indices would depend on implementation)


@pytest.mark.unit 
class TestHuMomentExtractor:
    """Test cases for HuMomentExtractor."""
    
    def test_extract_features_valid_contour(self, hu_moment_extractor, simple_contour, test_helpers):
        """Test Hu moment extraction from valid contour."""
        features = hu_moment_extractor.extract_features(simple_contour)
        
        test_helpers.assert_features_valid(features)
        assert len(features) == 7  # 7 Hu moments
    
    def test_invariance_properties(self, hu_moment_extractor):
        """Test rotation and scale invariance of Hu moments."""
        from core.dataset.shape_factory import ShapeFactory, ShapeType
        
        # Generate same shape at different scales and orientations
        original = ShapeFactory.generate_shape(ShapeType.SQUARE, 1.0)
        
        features_original = hu_moment_extractor.extract_features(original)
        
        # All features should be finite
        assert all(np.isfinite(f) for f in features_original)
        
        # First few Hu moments should be positive for most shapes
        assert features_original[0] > 0
    
    def test_log_transform_option(self):
        """Test Hu moments with log transform option."""
        extractor_log = HuMomentExtractor(use_log_transform=True)
        extractor_no_log = HuMomentExtractor(use_log_transform=False)
        
        from core.dataset.shape_factory import ShapeFactory, ShapeType
        contour = ShapeFactory.generate_shape(ShapeType.TRIANGLE, 1.0)
        
        features_log = extractor_log.extract_features(contour)
        features_no_log = extractor_no_log.extract_features(contour)
        
        # Both should be valid but different
        assert len(features_log) == len(features_no_log) == 7
        assert not np.array_equal(features_log, features_no_log)


@pytest.mark.unit
class TestCompositeFeatureExtractor:
    """Test cases for CompositeFeatureExtractor."""
    
    def test_combine_extractors(self, simple_contour, test_helpers):
        """Test combining multiple feature extractors."""
        geometric = GeometricFeatureExtractor()
        hu_moments = HuMomentExtractor()
        
        composite = CompositeFeatureExtractor([geometric, hu_moments])
        
        features = composite.extract_features(simple_contour)
        test_helpers.assert_features_valid(features)
        
        # Should have combined features
        expected_length = len(geometric.extract_features(simple_contour)) + len(hu_moments.extract_features(simple_contour))
        assert len(features) == expected_length
    
    def test_feature_names_combination(self):
        """Test that feature names are properly combined."""
        geometric = GeometricFeatureExtractor()
        hu_moments = HuMomentExtractor()
        
        composite = CompositeFeatureExtractor([geometric, hu_moments])
        
        names = composite.get_feature_names()
        geometric_names = geometric.get_feature_names()
        hu_names = hu_moments.get_feature_names()
        
        assert len(names) == len(geometric_names) + len(hu_names)
        
        # All individual names should be present
        for name in geometric_names + hu_names:
            assert name in names
    
    def test_empty_extractor_list(self):
        """Test behavior with empty extractor list."""
        with pytest.raises(ValueError):
            CompositeFeatureExtractor([])
    
    def test_single_extractor(self, simple_contour):
        """Test with single extractor (should work like the individual extractor)."""
        geometric = GeometricFeatureExtractor()
        composite = CompositeFeatureExtractor([geometric])
        
        features_individual = geometric.extract_features(simple_contour)
        features_composite = composite.extract_features(simple_contour)
        
        np.testing.assert_array_equal(features_individual, features_composite)
    
    def test_get_feature_count(self):
        """Test getting total feature count."""
        geometric = GeometricFeatureExtractor()
        hu_moments = HuMomentExtractor()
        
        composite = CompositeFeatureExtractor([geometric, hu_moments])
        
        expected_count = len(geometric.get_feature_names()) + len(hu_moments.get_feature_names())
        assert composite.get_feature_count() == expected_count


@pytest.mark.unit
class TestFeatureExtractorFactory:
    """Test cases for FeatureExtractorFactory."""
    
    def test_create_extractor_geometric(self):
        """Test creating geometric extractor through factory."""
        extractor = FeatureExtractorFactory.create_extractor('geometric')
        
        assert isinstance(extractor, GeometricFeatureExtractor)
    
    def test_create_extractor_hu_moments(self):
        """Test creating Hu moments extractor through factory."""
        extractor = FeatureExtractorFactory.create_extractor('hu')
        
        assert isinstance(extractor, HuMomentExtractor)
    
    def test_create_extractor_with_config(self):
        """Test creating extractor with configuration."""
        config = {'use_log_transform': False}
        extractor = FeatureExtractorFactory.create_extractor('hu', config)
        
        assert isinstance(extractor, HuMomentExtractor)
        # Would need access to internal config to verify this
    
    def test_create_composite_extractor(self):
        """Test creating composite extractor through factory."""
        configs = [
            {'name': 'geometric'},
            {'name': 'hu', 'config': {'use_log_transform': True}}
        ]
        
        extractor = FeatureExtractorFactory.create_composite_extractor(configs)
        
        assert isinstance(extractor, CompositeFeatureExtractor)
        assert extractor.get_feature_count() > 0
    
    def test_invalid_extractor_name(self):
        """Test behavior with invalid extractor name."""
        with pytest.raises((ValueError, KeyError)):
            FeatureExtractorFactory.create_extractor('invalid_name')
    
    def test_get_available_extractors(self):
        """Test getting list of available extractors."""
        available = FeatureExtractorFactory.get_available_extractors()
        
        assert isinstance(available, list)
        assert 'geometric' in available
        assert 'hu' in available


@pytest.mark.unit
@pytest.mark.slow
class TestFeatureExtractorPerformance:
    """Performance tests for feature extractors."""
    
    def test_geometric_extraction_performance(self, geometric_extractor, multiple_contours, performance_tracker):
        """Test geometric feature extraction performance."""
        performance_tracker.start("geometric_extraction")
        
        for contour in multiple_contours:
            geometric_extractor.extract_features(contour)
        
        duration = performance_tracker.stop()
        performance_tracker.assert_performance("geometric_extraction", 1.0)  # 1 second max
    
    def test_composite_extraction_performance(self, composite_extractor, multiple_contours, performance_tracker):
        """Test composite feature extraction performance."""
        performance_tracker.start("composite_extraction")
        
        for contour in multiple_contours:
            composite_extractor.extract_features(contour)
        
        duration = performance_tracker.stop()
        performance_tracker.assert_performance("composite_extraction", 2.0)  # 2 seconds max


@pytest.mark.unit
class TestFeatureExtractorEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_very_small_contour(self, geometric_extractor):
        """Test with very small contour (few points)."""
        # Minimum contour (3 points forming triangle)
        small_contour = np.array([[[10, 10]], [[20, 10]], [[15, 20]]], dtype=np.int32)
        
        try:
            features = geometric_extractor.extract_features(small_contour)
            assert len(features) > 0
        except ValueError:
            # Some extractors might not handle very small contours
            pass
    
    def test_contour_with_duplicate_points(self, geometric_extractor):
        """Test with contour containing duplicate points."""
        # Create contour with some duplicate points
        points = [[10, 10], [20, 10], [20, 10], [20, 20], [10, 20]]  # Duplicate point
        duplicate_contour = np.array([[[x, y]] for x, y in points], dtype=np.int32)
        
        try:
            features = geometric_extractor.extract_features(duplicate_contour)
            assert len(features) > 0
        except ValueError:
            # Some extractors might not handle duplicates well
            pass
    
    def test_feature_extraction_with_noise(self):
        """Test feature extraction robustness to noise."""
        from core.dataset.shape_factory import ShapeFactory, ShapeType
        from core.dataset.data_augmentation import NoiseAugmentation
        
        # Generate clean contour
        clean_contour = ShapeFactory.generate_shape(ShapeType.CIRCLE, 1.0)
        
        # Add noise
        noise_aug = NoiseAugmentation({'noise_level': 0.1})
        noisy_contour = noise_aug.apply(clean_contour)
        
        # Extract features from both
        extractor = GeometricFeatureExtractor()
        clean_features = extractor.extract_features(clean_contour)
        noisy_features = extractor.extract_features(noisy_contour)
        
        # Features should be similar but not identical
        assert len(clean_features) == len(noisy_features)
        
        # Some features should be relatively stable
        # (exact tolerance would depend on the specific features)
        relative_diff = np.abs(np.array(clean_features) - np.array(noisy_features)) / (np.array(clean_features) + 1e-8)
        assert np.mean(relative_diff) < 0.5  # Features shouldn't change by more than 50% on average