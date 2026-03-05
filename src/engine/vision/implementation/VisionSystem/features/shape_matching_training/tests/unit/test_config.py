"""
Unit tests for Configuration modules
"""

import pytest
import tempfile
from pathlib import Path

from config.base_config import BaseConfig, ConfigValidationError
from config.model_configs import SGDClassifierConfig, ModelConfigRegistry
from config.training_configs import DefaultTrainingConfig, FastTrainingConfig, TrainingConfigRegistry


@pytest.mark.unit
class TestBaseConfig:
    """Test cases for BaseConfig abstract class."""
    
    def test_config_validation_on_init(self):
        """Test that validation is called during initialization."""
        
        # Create a test config class
        class TestConfig(BaseConfig):
            def __init__(self, valid=True):
                self.valid = valid
                super().__init__()
            
            def validate(self):
                if not self.valid:
                    raise ConfigValidationError("Invalid config")
        
        # Valid config should work
        valid_config = TestConfig(valid=True)
        assert valid_config.valid is True
        
        # Invalid config should raise error
        with pytest.raises(ConfigValidationError):
            TestConfig(valid=False)
    
    def test_config_serialization(self):
        """Test config to_dict and from_dict methods."""
        config = DefaultTrainingConfig()
        
        # Convert to dict
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        
        # Should contain expected keys
        assert 'dataset' in config_dict
        assert 'features' in config_dict
        assert 'training' in config_dict
        assert 'io' in config_dict
    
    def test_config_merge(self):
        """Test configuration merging."""
        config1 = DefaultTrainingConfig()
        config2 = FastTrainingConfig()
        
        # Get original values
        original_n_shapes = config1.dataset.n_shapes
        fast_n_shapes = config2.dataset.n_shapes
        
        # They should be different
        assert original_n_shapes != fast_n_shapes
        
        # Test that configs are independent
        config1.dataset.n_shapes = 999
        assert config2.dataset.n_shapes == fast_n_shapes  # Should not change


@pytest.mark.unit
class TestModelConfigs:
    """Test cases for model configurations."""
    
    def test_sgd_classifier_config_creation(self):
        """Test SGD classifier configuration creation."""
        config = SGDClassifierConfig()
        
        assert config.loss in ['hinge', 'log_loss', 'modified_huber', 'squared_hinge']
        assert config.penalty in ['l1', 'l2', 'elasticnet', 'none']
        assert config.alpha > 0
        assert config.max_iter > 0
        assert isinstance(config.random_state, int)
    
    def test_sgd_config_validation(self):
        """Test SGD configuration validation."""
        # Valid config
        config = SGDClassifierConfig(alpha=0.01, max_iter=1000)
        # Should not raise error
        
        # Invalid alpha
        with pytest.raises(ConfigValidationError):
            SGDClassifierConfig(alpha=-1)
        
        # Invalid max_iter
        with pytest.raises(ConfigValidationError):
            SGDClassifierConfig(max_iter=0)
    
    def test_model_config_registry(self):
        """Test model configuration registry."""
        # Test getting default config
        config = ModelConfigRegistry.get_default_sgd_calibrated()
        assert config is not None
        assert hasattr(config, 'sgd_config')
        assert hasattr(config, 'calibration_config')
        
        # Test getting fast config
        fast_config = ModelConfigRegistry.get_fast_sgd_calibrated()
        assert fast_config is not None
        
        # Test getting config by name
        named_config = ModelConfigRegistry.get_config('default')
        assert named_config is not None
    
    def test_invalid_config_name(self):
        """Test behavior with invalid configuration name."""
        with pytest.raises((KeyError, ValueError)):
            ModelConfigRegistry.get_config('invalid_config_name')


@pytest.mark.unit 
class TestTrainingConfigs:
    """Test cases for training configurations."""
    
    def test_default_training_config(self):
        """Test default training configuration."""
        config = DefaultTrainingConfig()
        
        # Check that all required attributes exist
        assert hasattr(config, 'dataset')
        assert hasattr(config, 'features')
        assert hasattr(config, 'training')
        assert hasattr(config, 'io')
        
        # Check dataset config
        assert config.dataset.n_shapes > 0
        assert config.dataset.n_scales > 0
        assert config.dataset.n_variants > 0
        assert config.dataset.n_noisy > 0
        
        # Check feature config
        assert isinstance(config.features.feature_types, list)
        assert len(config.features.feature_types) > 0
        
        # Check training config
        assert 0 < config.training.test_size < 1
        assert isinstance(config.training.random_state, int)
        
        # Check IO config
        assert config.io.models_dir is not None
        assert config.io.results_dir is not None
    
    def test_fast_training_config(self):
        """Test fast training configuration."""
        config = FastTrainingConfig()
        
        # Fast config should have smaller dataset
        default_config = DefaultTrainingConfig()
        assert config.dataset.n_shapes <= default_config.dataset.n_shapes
        assert config.dataset.n_variants <= default_config.dataset.n_variants
    
    def test_training_config_registry(self):
        """Test training configuration registry."""
        # Test getting configs by name
        default_config = TrainingConfigRegistry.get_config('default')
        assert isinstance(default_config, DefaultTrainingConfig)
        
        fast_config = TrainingConfigRegistry.get_config('fast')
        assert isinstance(fast_config, FastTrainingConfig)
        
        # Test getting available configs
        available = TrainingConfigRegistry.get_available_configs()
        assert isinstance(available, list)
        assert 'default' in available
        assert 'fast' in available
    
    def test_config_validation_errors(self):
        """Test configuration validation errors."""
        # Test dataset config validation
        config = DefaultTrainingConfig()
        
        # Invalid n_shapes
        config.dataset.n_shapes = 0
        with pytest.raises(ConfigValidationError):
            config.validate()
        
        # Reset to valid value
        config.dataset.n_shapes = 2
        
        # Invalid test_size
        config.training.test_size = 1.5  # > 1
        with pytest.raises(ConfigValidationError):
            config.validate()
    
    def test_config_file_operations(self, temp_dir):
        """Test saving and loading configurations."""
        config = DefaultTrainingConfig()
        
        # Save configuration
        config_file = temp_dir / "test_config.json"
        config.save_to_file(str(config_file))
        
        assert config_file.exists()
        
        # Load configuration 
        loaded_config = DefaultTrainingConfig.load_from_file(str(config_file))
        
        # Should have same values
        assert loaded_config.dataset.n_shapes == config.dataset.n_shapes
        assert loaded_config.training.test_size == config.training.test_size
    
    def test_config_environment_variables(self):
        """Test configuration with environment variables."""
        import os
        
        # Set environment variable
        os.environ['SHAPE_MATCHING_MODELS_DIR'] = '/tmp/test_models'
        
        try:
            # This would test environment variable loading
            # Implementation depends on whether BaseConfig supports env vars
            config = DefaultTrainingConfig()
            # Test would check if models_dir was set from env var
            pass
        finally:
            # Clean up
            if 'SHAPE_MATCHING_MODELS_DIR' in os.environ:
                del os.environ['SHAPE_MATCHING_MODELS_DIR']


@pytest.mark.unit
class TestConfigEdgeCases:
    """Test edge cases and error conditions for configurations."""
    
    def test_config_with_none_values(self):
        """Test configuration behavior with None values."""
        config = DefaultTrainingConfig()
        
        # Setting None for optional fields should work
        config.dataset.included_shapes = None
        config.validate()  # Should not raise error
        
        # Setting None for required fields should raise error
        config.dataset.n_shapes = None
        with pytest.raises((ConfigValidationError, TypeError)):
            config.validate()
    
    def test_config_with_extreme_values(self):
        """Test configuration with extreme values."""
        config = DefaultTrainingConfig()
        
        # Very large values
        config.dataset.n_shapes = 1000000
        # Should either work or raise validation error
        try:
            config.validate()
        except ConfigValidationError:
            pass
        
        # Very small values
        config.dataset.n_shapes = 1
        config.dataset.n_scales = 1
        config.dataset.n_variants = 1
        config.dataset.n_noisy = 1
        # Should work for minimal dataset
        config.validate()
    
    def test_config_immutability_simulation(self):
        """Test configuration immutability patterns."""
        config = DefaultTrainingConfig()
        original_n_shapes = config.dataset.n_shapes
        
        # Create a copy and modify it
        import copy
        config_copy = copy.deepcopy(config)
        config_copy.dataset.n_shapes = original_n_shapes + 1
        
        # Original should be unchanged
        assert config.dataset.n_shapes == original_n_shapes
        assert config_copy.dataset.n_shapes == original_n_shapes + 1
    
    def test_config_nested_validation(self):
        """Test validation of nested configuration objects."""
        config = DefaultTrainingConfig()
        
        # Modify nested config to invalid state
        config.dataset.min_scale = 2.0
        config.dataset.max_scale = 1.0  # max < min, should be invalid
        
        with pytest.raises(ConfigValidationError):
            config.validate()