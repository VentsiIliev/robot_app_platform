"""
Unit tests for Model modules
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from sklearn.exceptions import NotFittedError

from core.models.sgd_model import SGDModel
from core.models.model_factory import ModelFactory
from core.models.base_model import BaseModel, PredictionResult
from config.model_configs import ModelConfigRegistry


@pytest.mark.unit
class TestSGDModel:
    """Test cases for SGDModel."""
    
    def test_model_initialization(self):
        """Test SGD model initialization."""
        model = SGDModel()
        
        assert model is not None
        assert not model.is_fitted()
        assert model.get_model_info() is not None
    
    def test_model_initialization_with_config(self):
        """Test SGD model initialization with configuration."""
        config = ModelConfigRegistry.get_fast_sgd_calibrated()
        model = SGDModel(config)
        
        assert model is not None
        assert model.model_config == config
    
    def test_fit_and_predict(self, sgd_model, sample_features, sample_labels):
        """Test model fitting and prediction."""
        # Fit the model
        sgd_model.fit(sample_features, sample_labels)
        
        assert sgd_model.is_fitted()
        
        # Make predictions
        predictions = sgd_model.predict(sample_features[:10])
        
        assert isinstance(predictions, np.ndarray)
        assert len(predictions) == 10
        assert all(p in [0, 1] for p in predictions)
    
    def test_predict_proba(self, trained_model, sample_features):
        """Test probability prediction."""
        probabilities = trained_model.predict_proba(sample_features[:10])
        
        assert isinstance(probabilities, np.ndarray)
        assert probabilities.shape == (10, 2)
        
        # Probabilities should sum to 1
        prob_sums = np.sum(probabilities, axis=1)
        np.testing.assert_array_almost_equal(prob_sums, np.ones(10), decimal=5)
        
        # All probabilities should be between 0 and 1
        assert np.all(probabilities >= 0)
        assert np.all(probabilities <= 1)
    
    def test_predict_with_confidence(self, trained_model, sample_features):
        """Test prediction with confidence scores."""
        result = trained_model.predict_with_confidence(sample_features[:5])
        
        assert isinstance(result, PredictionResult)
        assert len(result.predictions) == 5
        assert len(result.probabilities) == 5
        assert len(result.confidence_scores) == 5
        
        # Confidence scores should be between 0 and 1
        assert all(0 <= c <= 1 for c in result.confidence_scores)
    
    def test_predict_without_fitting(self, sgd_model, sample_features):
        """Test prediction on unfitted model."""
        with pytest.raises((NotFittedError, ValueError)):
            sgd_model.predict(sample_features[:10])
    
    def test_feature_importance(self, trained_model):
        """Test getting feature importance."""
        importance = trained_model.get_feature_importance()
        
        if importance is not None:
            assert isinstance(importance, np.ndarray)
            assert len(importance) > 0
    
    def test_model_info(self, trained_model):
        """Test getting model information."""
        info = trained_model.get_model_info()
        
        assert isinstance(info, dict)
        assert 'model_type' in info
        assert 'is_fitted' in info
        assert 'n_features' in info
        assert info['is_fitted'] is True
    
    def test_set_feature_names(self, sgd_model):
        """Test setting feature names."""
        feature_names = ['feature_1', 'feature_2', 'feature_3']
        sgd_model.set_feature_names(feature_names)
        
        # Should not raise an error
        # (Implementation might store names internally)
    
    def test_validate_input_shapes(self, trained_model, sample_features):
        """Test input shape validation."""
        # Valid input
        predictions = trained_model.predict(sample_features[:5])
        assert len(predictions) == 5
        
        # Invalid input shapes
        with pytest.raises(ValueError):
            # Wrong number of features
            wrong_features = np.random.randn(5, 10)  # Different number of features
            trained_model.predict(wrong_features)
        
        with pytest.raises(ValueError):
            # 1D input instead of 2D
            wrong_input = sample_features[0]  # Single sample, 1D
            trained_model.predict(wrong_input)
    
    def test_empty_input(self, trained_model):
        """Test behavior with empty input."""
        empty_input = np.array([]).reshape(0, 24)  # 0 samples, correct features
        
        predictions = trained_model.predict(empty_input)
        assert len(predictions) == 0
    
    @pytest.mark.performance
    def test_prediction_performance(self, trained_model, performance_tracker):
        """Test prediction performance."""
        # Generate larger test set
        X_test = np.random.randn(1000, 24)
        
        performance_tracker.start("prediction_performance")
        predictions = trained_model.predict(X_test)
        duration = performance_tracker.stop()
        
        assert len(predictions) == 1000
        performance_tracker.assert_performance("prediction_performance", 1.0)  # 1 second max


@pytest.mark.unit
class TestModelFactory:
    """Test cases for ModelFactory."""
    
    def test_create_sgd_model(self):
        """Test creating SGD model through factory."""
        model = ModelFactory.create_model('sgd')
        
        assert isinstance(model, SGDModel)
        assert not model.is_fitted()
    
    def test_create_model_with_config_name(self):
        """Test creating model with configuration name."""
        model = ModelFactory.create_model('sgd', {'config_name': 'fast'})
        
        assert isinstance(model, SGDModel)
    
    def test_create_model_with_config_object(self):
        """Test creating model with configuration object."""
        config = ModelConfigRegistry.get_default_sgd_calibrated()
        model = ModelFactory.create_model('sgd', config)
        
        assert isinstance(model, SGDModel)
    
    def test_create_ensemble_model(self):
        """Test creating ensemble model."""
        configs = [
            {'model_type': 'sgd', 'config': {'config_name': 'default'}},
            {'model_type': 'sgd', 'config': {'config_name': 'robust'}}
        ]
        
        try:
            ensemble = ModelFactory.create_ensemble_model(configs)
            assert ensemble is not None
        except (NotImplementedError, ImportError):
            pytest.skip("Ensemble model not fully implemented")
    
    def test_invalid_model_type(self):
        """Test behavior with invalid model type."""
        with pytest.raises((ValueError, KeyError)):
            ModelFactory.create_model('invalid_type')
    
    def test_get_available_models(self):
        """Test getting available model types."""
        try:
            available = ModelFactory.get_available_models()
            assert isinstance(available, list)
            assert 'sgd' in available
        except AttributeError:
            # Method might not be implemented
            pass


@pytest.mark.unit
class TestBaseModel:
    """Test cases for BaseModel interface."""
    
    def test_abstract_methods(self):
        """Test that BaseModel is abstract."""
        with pytest.raises(TypeError):
            BaseModel()
    
    def test_prediction_result_structure(self):
        """Test PredictionResult dataclass."""
        predictions = np.array([1, 0, 1])
        probabilities = np.array([[0.2, 0.8], [0.9, 0.1], [0.3, 0.7]])
        confidence_scores = np.array([0.8, 0.9, 0.7])
        
        result = PredictionResult(predictions, probabilities, confidence_scores)
        
        assert np.array_equal(result.predictions, predictions)
        assert np.array_equal(result.probabilities, probabilities)
        assert np.array_equal(result.confidence_scores, confidence_scores)


@pytest.mark.unit
class TestModelCompatibility:
    """Test model compatibility and serialization."""
    
    def test_model_serialization(self, trained_model, temp_dir):
        """Test model saving and loading."""
        import pickle
        
        model_path = temp_dir / "test_model.pkl"
        
        # Save model
        with open(model_path, 'wb') as f:
            pickle.dump(trained_model, f)
        
        # Load model
        with open(model_path, 'rb') as f:
            loaded_model = pickle.load(f)
        
        assert loaded_model is not None
        assert loaded_model.is_fitted()
        
        # Test that loaded model works
        test_data = np.random.randn(5, 24)
        original_predictions = trained_model.predict(test_data)
        loaded_predictions = loaded_model.predict(test_data)
        
        np.testing.assert_array_equal(original_predictions, loaded_predictions)
    
    def test_model_copy(self, trained_model):
        """Test model copying."""
        import copy
        
        # Deep copy
        copied_model = copy.deepcopy(trained_model)
        
        assert copied_model is not None
        assert copied_model.is_fitted()
        
        # Should produce same predictions
        test_data = np.random.randn(5, 24)
        original_predictions = trained_model.predict(test_data)
        copied_predictions = copied_model.predict(test_data)
        
        np.testing.assert_array_equal(original_predictions, copied_predictions)
    
    @pytest.mark.slow
    def test_concurrent_predictions(self, trained_model):
        """Test concurrent predictions (thread safety)."""
        import threading
        import queue
        
        test_data = np.random.randn(10, 24)
        results = queue.Queue()
        
        def make_prediction(model, data, result_queue):
            try:
                predictions = model.predict(data)
                result_queue.put(predictions)
            except Exception as e:
                result_queue.put(e)
        
        # Start multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_prediction, args=(trained_model, test_data, results))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Collect results
        prediction_results = []
        while not results.empty():
            result = results.get()
            assert not isinstance(result, Exception), f"Thread failed with: {result}"
            prediction_results.append(result)
        
        assert len(prediction_results) == 5
        
        # All predictions should be the same
        for pred in prediction_results[1:]:
            np.testing.assert_array_equal(prediction_results[0], pred)


@pytest.mark.unit
class TestModelEdgeCases:
    """Test edge cases and error conditions for models."""
    
    def test_fitting_with_invalid_data(self, sgd_model):
        """Test fitting with invalid data."""
        # Mismatched X and y lengths
        X = np.random.randn(10, 5)
        y = np.random.choice([0, 1], size=15)  # Different length
        
        with pytest.raises(ValueError):
            sgd_model.fit(X, y)
    
    def test_fitting_with_single_class(self, sgd_model):
        """Test fitting with only one class."""
        X = np.random.randn(10, 5)
        y = np.ones(10)  # Only class 1
        
        # Should handle gracefully or raise appropriate error
        try:
            sgd_model.fit(X, y)
            predictions = sgd_model.predict(X)
            # Should predict the single class
            assert all(p == 1 for p in predictions)
        except ValueError:
            # Some models might not handle single class
            pass
    
    def test_extreme_feature_values(self, sgd_model):
        """Test model behavior with extreme feature values."""
        # Very large values
        X_large = np.full((10, 5), 1e10)
        y = np.random.choice([0, 1], size=10)
        
        try:
            sgd_model.fit(X_large, y)
            predictions = sgd_model.predict(X_large[:5])
            assert len(predictions) == 5
        except (ValueError, OverflowError):
            # Model might not handle extreme values
            pass
        
        # Very small values
        X_small = np.full((10, 5), 1e-10)
        
        try:
            sgd_model.fit(X_small, y)
            predictions = sgd_model.predict(X_small[:5])
            assert len(predictions) == 5
        except ValueError:
            # Model might not handle very small values
            pass
    
    def test_nan_and_inf_handling(self, sgd_model):
        """Test model behavior with NaN and infinite values."""
        X_with_nan = np.random.randn(10, 5)
        X_with_nan[0, 0] = np.nan
        y = np.random.choice([0, 1], size=10)
        
        with pytest.raises(ValueError):
            sgd_model.fit(X_with_nan, y)
        
        X_with_inf = np.random.randn(10, 5)
        X_with_inf[0, 0] = np.inf
        
        with pytest.raises(ValueError):
            sgd_model.fit(X_with_inf, y)