"""
pytest Configuration and Fixtures

This module provides shared test fixtures and configuration for the entire test suite.
"""

import pytest
import numpy as np
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Generator
from unittest.mock import Mock, MagicMock

# Add the module to the path for testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.dataset.shape_factory import ShapeFactory, ShapeType
from core.dataset.synthetic_dataset import SyntheticDataset, SyntheticContour
from core.dataset.pair_generator import PairGenerator
from core.features.geometric_features import GeometricFeatureExtractor
from core.features.moment_features import HuMomentExtractor
from core.features.base_extractor import CompositeFeatureExtractor
from core.models.sgd_model import SGDModel
from config.model_configs import ModelConfigRegistry
from config.training_configs import DefaultTrainingConfig


@pytest.fixture(scope="session")
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    temp_path = Path(tempfile.mkdtemp(prefix="shape_matching_tests_"))
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def simple_contour() -> np.ndarray:
    """Generate a simple square contour for testing."""
    return ShapeFactory.generate_shape(ShapeType.SQUARE, scale=1.0, img_size=(256, 256))


@pytest.fixture
def circle_contour() -> np.ndarray:
    """Generate a circle contour for testing."""
    return ShapeFactory.generate_shape(ShapeType.CIRCLE, scale=1.0, img_size=(256, 256))


@pytest.fixture
def multiple_contours() -> List[np.ndarray]:
    """Generate multiple different contours for testing."""
    contours = []
    shapes = [ShapeType.CIRCLE, ShapeType.SQUARE, ShapeType.TRIANGLE]
    
    for shape_type in shapes:
        for scale in [0.8, 1.0, 1.2]:
            contour = ShapeFactory.generate_shape(shape_type, scale, (256, 256))
            contours.append(contour)
    
    return contours


@pytest.fixture
def synthetic_contours() -> List[SyntheticContour]:
    """Generate synthetic contours with metadata for testing."""
    contours = []
    shapes = [ShapeType.CIRCLE, ShapeType.SQUARE]
    
    for i, shape_type in enumerate(shapes):
        for j, scale in enumerate([0.8, 1.0]):
            contour = ShapeFactory.generate_shape(shape_type, scale, (256, 256))
            synthetic = SyntheticContour(
                contour=contour,
                object_id=f"{shape_type.value}_scale{j}",
                shape_type=shape_type,
                scale=scale,
                variant_name=f"test_variant_{i}_{j}",
                parameters={"test_param": f"value_{i}_{j}"}
            )
            contours.append(synthetic)
    
    return contours


@pytest.fixture
def training_pairs() -> Tuple[List[Tuple[np.ndarray, np.ndarray]], List[int]]:
    """Generate training pairs with labels for testing."""
    # Generate some contours
    circle1 = ShapeFactory.generate_shape(ShapeType.CIRCLE, 1.0, (256, 256))
    circle2 = ShapeFactory.generate_shape(ShapeType.CIRCLE, 1.1, (256, 256))
    square1 = ShapeFactory.generate_shape(ShapeType.SQUARE, 1.0, (256, 256))
    square2 = ShapeFactory.generate_shape(ShapeType.SQUARE, 1.1, (256, 256))
    
    # Create pairs
    pairs = [
        (circle1, circle2),  # Positive pair
        (square1, square2),  # Positive pair
        (circle1, square1),  # Negative pair
        (circle2, square2),  # Negative pair
    ]
    
    labels = [1, 1, 0, 0]  # 1 = positive, 0 = negative
    
    return pairs, labels


@pytest.fixture
def geometric_extractor() -> GeometricFeatureExtractor:
    """Create a geometric feature extractor for testing."""
    return GeometricFeatureExtractor()


@pytest.fixture
def hu_moment_extractor() -> HuMomentExtractor:
    """Create a Hu moment extractor for testing."""
    return HuMomentExtractor()


@pytest.fixture
def composite_extractor() -> CompositeFeatureExtractor:
    """Create a composite feature extractor for testing."""
    extractors = [
        GeometricFeatureExtractor(),
        HuMomentExtractor()
    ]
    return CompositeFeatureExtractor(extractors)


@pytest.fixture
def sgd_model() -> SGDModel:
    """Create an SGD model for testing."""
    config = ModelConfigRegistry.get_fast_sgd_calibrated()
    return SGDModel(config)


@pytest.fixture
def trained_model(sgd_model, composite_extractor, training_pairs) -> SGDModel:
    """Create a trained model for testing."""
    pairs, labels = training_pairs
    
    # Extract features
    features = []
    for contour1, contour2 in pairs:
        feat1 = composite_extractor.extract_features(contour1)
        feat2 = composite_extractor.extract_features(contour2)
        combined_features = feat1 + feat2
        features.append(combined_features)
    
    X = np.array(features)
    y = np.array(labels)
    
    # Train the model
    sgd_model.fit(X, y)
    return sgd_model


@pytest.fixture
def default_config() -> DefaultTrainingConfig:
    """Create a default training configuration for testing."""
    return DefaultTrainingConfig()


@pytest.fixture
def mock_model() -> Mock:
    """Create a mock model for testing."""
    model = MagicMock()
    model.predict.return_value = np.array([1, 0, 1, 0])
    model.predict_proba.return_value = np.array([[0.2, 0.8], [0.9, 0.1], [0.3, 0.7], [0.8, 0.2]])
    model.is_fitted.return_value = True
    return model


@pytest.fixture
def sample_features() -> np.ndarray:
    """Generate sample feature matrix for testing."""
    np.random.seed(42)  # For reproducible tests
    return np.random.randn(100, 24)  # 100 samples, 24 features


@pytest.fixture
def sample_labels() -> np.ndarray:
    """Generate sample labels for testing."""
    np.random.seed(42)  # For reproducible tests
    return np.random.choice([0, 1], size=100)


@pytest.fixture
def small_dataset() -> SyntheticDataset:
    """Create a small synthetic dataset for testing."""
    return SyntheticDataset(
        n_shapes=2,
        n_scales=2, 
        n_variants=2,
        n_noisy=2,
        shape_types=[ShapeType.CIRCLE, ShapeType.SQUARE],
        img_size=(128, 128)
    )


@pytest.fixture
def pair_generator() -> PairGenerator:
    """Create a pair generator for testing."""
    return PairGenerator(
        include_hard_negatives=True,
        balance_strategy='downsample',
        random_state=42
    )


# Test markers
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "performance: marks tests as performance tests")


# Custom assertions
class TestHelpers:
    """Helper methods for testing."""
    
    @staticmethod
    def assert_contour_valid(contour: np.ndarray) -> None:
        """Assert that a contour is valid."""
        assert contour is not None
        assert isinstance(contour, np.ndarray)
        assert len(contour.shape) == 3
        assert contour.shape[1] == 1
        assert contour.shape[2] == 2
        assert len(contour) >= 3  # Minimum points for a contour
    
    @staticmethod
    def assert_features_valid(features: List[float]) -> None:
        """Assert that extracted features are valid."""
        assert features is not None
        assert isinstance(features, list)
        assert len(features) > 0
        assert all(isinstance(f, (int, float)) for f in features)
        assert all(np.isfinite(f) for f in features)
    
    @staticmethod
    def assert_model_predictions_valid(predictions: np.ndarray) -> None:
        """Assert that model predictions are valid."""
        assert predictions is not None
        assert isinstance(predictions, np.ndarray)
        assert len(predictions.shape) == 1
        assert all(p in [0, 1] for p in predictions)


@pytest.fixture
def test_helpers() -> TestHelpers:
    """Provide test helper methods."""
    return TestHelpers()


# Performance tracking
@pytest.fixture
def performance_tracker():
    """Track performance metrics during tests."""
    import time
    
    class PerformanceTracker:
        def __init__(self):
            self.timings = {}
            self.start_time = None
        
        def start(self, operation_name: str):
            self.start_time = time.time()
            self.operation_name = operation_name
        
        def stop(self):
            if self.start_time:
                duration = time.time() - self.start_time
                self.timings[self.operation_name] = duration
                self.start_time = None
                return duration
            return None
        
        def get_timing(self, operation_name: str) -> float:
            return self.timings.get(operation_name, 0.0)
        
        def assert_performance(self, operation_name: str, max_duration: float):
            duration = self.get_timing(operation_name)
            assert duration <= max_duration, f"{operation_name} took {duration:.3f}s, expected <= {max_duration:.3f}s"
    
    return PerformanceTracker()